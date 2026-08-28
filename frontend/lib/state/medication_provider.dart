/// Medication State Management Provider using Riverpod.
///
/// Features:
/// - Offline-first caching via LocalCacheService
/// - Optimistic dose logging with write-queue replay
/// - Inline interaction warning exposure
library;

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/api_client.dart';
import '../services/local_cache.dart';
import 'auth_provider.dart';

class MedicationState {
  final bool isLoading;
  final bool isOffline;
  final List<Map<String, dynamic>> medications;
  final List<Map<String, dynamic>> drugSearchResults;
  final bool isSearching;
  final Map<String, dynamic>? lastInteractionCheck;
  final String? errorMessage;

  const MedicationState({
    this.isLoading = false,
    this.isOffline = false,
    this.medications = const [],
    this.drugSearchResults = const [],
    this.isSearching = false,
    this.lastInteractionCheck,
    this.errorMessage,
  });

  List<Map<String, dynamic>> get activeMedications =>
      medications.where((m) => m['is_active'] == true).toList();

  List<Map<String, dynamic>> get inactiveMedications =>
      medications.where((m) => m['is_active'] == false).toList();

  MedicationState copyWith({
    bool? isLoading,
    bool? isOffline,
    List<Map<String, dynamic>>? medications,
    List<Map<String, dynamic>>? drugSearchResults,
    bool? isSearching,
    Map<String, dynamic>? lastInteractionCheck,
    String? errorMessage,
  }) {
    return MedicationState(
      isLoading: isLoading ?? this.isLoading,
      isOffline: isOffline ?? this.isOffline,
      medications: medications ?? this.medications,
      drugSearchResults: drugSearchResults ?? this.drugSearchResults,
      isSearching: isSearching ?? this.isSearching,
      lastInteractionCheck: lastInteractionCheck ?? this.lastInteractionCheck,
      errorMessage: errorMessage,
    );
  }
}

class MedicationNotifier extends StateNotifier<MedicationState> {
  final ApiClient _apiClient;
  final LocalCacheService _cache;
  final String _userId;

  MedicationNotifier({
    required ApiClient apiClient,
    required LocalCacheService cache,
    required String userId,
  })  : _apiClient = apiClient,
        _cache = cache,
        _userId = userId,
        super(const MedicationState(isLoading: true)) {
    loadMedications();
  }

  Future<void> loadMedications() async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      // 1. Try fetching live from API
      final liveMeds = await _apiClient.listMedications(includeInactive: true);
      // Cache the result
      await _cache.cacheMedications(_userId, liveMeds);

      // 2. Replay any pending offline writes
      await _replayOfflineQueue();

      state = state.copyWith(
        isLoading: false,
        isOffline: false,
        medications: liveMeds,
        errorMessage: null,
      );
    } catch (e) {
      // Fallback to offline cache
      debugPrint('Failed to load medications from network, falling back to cache: $e');
      final cached = await _cache.getCachedMedications(_userId);
      state = state.copyWith(
        isLoading: false,
        isOffline: true,
        medications: cached,
        errorMessage: 'Working offline — showing cached medications',
      );
    }
  }

  Future<void> searchCatalog(String query) async {
    if (query.trim().isEmpty) {
      state = state.copyWith(drugSearchResults: [], isSearching: false);
      return;
    }
    state = state.copyWith(isSearching: true);
    try {
      final results = await _apiClient.searchDrugs(query: query.trim());
      state = state.copyWith(drugSearchResults: results, isSearching: false);
    } catch (e) {
      state = state.copyWith(drugSearchResults: [], isSearching: false);
    }
  }

  Future<Map<String, dynamic>?> addMedication({
    required String drugId,
    required double dosageAmount,
    required String dosageUnit,
    required List<Map<String, dynamic>> schedules,
    String? notes,
    String inputMethod = 'manual',
  }) async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final res = await _apiClient.addMedication(
        drugId: drugId,
        dosageAmount: dosageAmount,
        dosageUnit: dosageUnit,
        schedules: schedules,
        notes: notes,
        inputMethod: inputMethod,
      );

      final interactionCheck = res['interaction_check'] as Map<String, dynamic>?;

      // Refresh list
      await loadMedications();
      state = state.copyWith(lastInteractionCheck: interactionCheck);
      return res;
    } catch (e) {
      final msg = e is ApiException ? e.message : e.toString();
      state = state.copyWith(isLoading: false, errorMessage: msg);
      return null;
    }
  }

  Future<bool> deactivateMedication(String entryId) async {
    try {
      await _apiClient.patchMedication(entryId, deactivate: true);
      await loadMedications();
      return true;
    } catch (e) {
      final msg = e is ApiException ? e.message : e.toString();
      state = state.copyWith(errorMessage: msg);
      return false;
    }
  }

  Future<bool> logDose({
    required String entryId,
    required String status,
    required String scheduledTime,
    String? takenAt,
    String? notes,
  }) async {
    final payload = {
      'entry_id': entryId,
      'status': status,
      'scheduled_time': scheduledTime,
      if (takenAt != null) 'taken_at': takenAt,
      if (notes != null) 'notes': notes,
    };

    try {
      await _apiClient.logDose(
        entryId,
        status: status,
        scheduledTime: scheduledTime,
        takenAt: takenAt,
        notes: notes,
      );
      return true;
    } catch (e) {
      // Queue offline
      debugPrint('Logging dose offline: $e');
      await _cache.queueWriteAction(
        OfflineWriteAction(
          actionType: 'log_dose',
          payload: payload,
          queuedAt: DateTime.now().toIso8601String(),
        ),
      );
      return true;
    }
  }

  Future<void> _replayOfflineQueue() async {
    try {
      final queue = await _cache.getWriteQueue();
      if (queue.isEmpty) return;

      for (final action in queue) {
        if (action.actionType == 'log_dose') {
          final p = action.payload;
          await _apiClient.logDose(
            p['entry_id'] as String,
            status: p['status'] as String,
            scheduledTime: p['scheduled_time'] as String,
            takenAt: p['taken_at'] as String?,
            notes: p['notes'] as String?,
          );
        } else if (action.actionType == 'acknowledge_alert') {
          final alertId = action.payload['alert_id'] as String;
          await _apiClient.acknowledgeAlert(alertId);
        }
      }
      await _cache.clearWriteQueue();
      debugPrint('Successfully replayed ${queue.length} offline actions');
    } catch (e) {
      debugPrint('Offline write replay encountered error: $e');
    }
  }
}

final localCacheProvider = Provider<LocalCacheService>((ref) {
  final cache = LocalCacheService();
  cache.init();
  return cache;
});

final medicationProvider = StateNotifierProvider<MedicationNotifier, MedicationState>((ref) {
  final client = ref.watch(apiClientProvider);
  final cache = ref.watch(localCacheProvider);
  final auth = ref.watch(authProvider);
  final userId = auth.userId ?? 'anonymous';

  return MedicationNotifier(apiClient: client, cache: cache, userId: userId);
});
