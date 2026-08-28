/// Alert State Management Provider using Riverpod.
///
/// Features:
/// - Manages interaction alerts list
/// - Tracks unacknowledged major alerts that require user action
/// - Handles acknowledgment flow with offline fallback
library;

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/api_client.dart';
import '../services/local_cache.dart';
import 'auth_provider.dart';
import 'medication_provider.dart';

class AlertState {
  final bool isLoading;
  final bool isOffline;
  final List<Map<String, dynamic>> alerts;
  final String? errorMessage;

  const AlertState({
    this.isLoading = false,
    this.isOffline = false,
    this.alerts = const [],
    this.errorMessage,
  });

  List<Map<String, dynamic>> get unacknowledgedAlerts =>
      alerts.where((a) => a['acknowledged'] == false).toList();

  List<Map<String, dynamic>> get pendingMajorAlerts =>
      alerts.where((a) => a['acknowledged'] == false && a['requires_acknowledgment'] == true).toList();

  AlertState copyWith({
    bool? isLoading,
    bool? isOffline,
    List<Map<String, dynamic>>? alerts,
    String? errorMessage,
  }) {
    return AlertState(
      isLoading: isLoading ?? this.isLoading,
      isOffline: isOffline ?? this.isOffline,
      alerts: alerts ?? this.alerts,
      errorMessage: errorMessage,
    );
  }
}

class AlertNotifier extends StateNotifier<AlertState> {
  final ApiClient _apiClient;
  final LocalCacheService _cache;
  final String _userId;

  AlertNotifier({
    required ApiClient apiClient,
    required LocalCacheService cache,
    required String userId,
  })  : _apiClient = apiClient,
        _cache = cache,
        _userId = userId,
        super(const AlertState(isLoading: true)) {
    loadAlerts();
  }

  Future<void> loadAlerts() async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final liveAlerts = await _apiClient.listAlerts();
      await _cache.cacheAlerts(_userId, liveAlerts);
      state = state.copyWith(
        isLoading: false,
        isOffline: false,
        alerts: liveAlerts,
        errorMessage: null,
      );
    } catch (e) {
      debugPrint('Failed to load alerts from network, falling back to cache: $e');
      final cached = await _cache.getCachedAlerts(_userId);
      state = state.copyWith(
        isLoading: false,
        isOffline: true,
        alerts: cached,
        errorMessage: 'Showing cached safety alerts',
      );
    }
  }

  Future<bool> acknowledgeAlert(String alertId) async {
    try {
      await _apiClient.acknowledgeAlert(alertId);
      await loadAlerts();
      return true;
    } catch (e) {
      // Optimistic update + queue offline
      debugPrint('Acknowledging alert offline: $e');
      await _cache.queueWriteAction(
        OfflineWriteAction(
          actionType: 'acknowledge_alert',
          payload: {'alert_id': alertId},
          queuedAt: DateTime.now().toIso8601String(),
        ),
      );

      final updated = state.alerts.map((a) {
        if (a['alert_id'] == alertId) {
          return {
            ...a,
            'acknowledged': true,
            'acknowledged_at': DateTime.now().toIso8601String(),
          };
        }
        return a;
      }).toList();

      state = state.copyWith(alerts: updated);
      return true;
    }
  }
}

final alertProvider = StateNotifierProvider<AlertNotifier, AlertState>((ref) {
  final client = ref.watch(apiClientProvider);
  final cache = ref.watch(localCacheProvider);
  final auth = ref.watch(authProvider);
  final userId = auth.userId ?? 'anonymous';

  return AlertNotifier(apiClient: client, cache: cache, userId: userId);
});
