/// History Timeline State Management Provider using Riverpod.
///
/// Features:
/// - Cursor-based timeline pagination for unified doses + alerts feed
/// - PDF Export generation trigger
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/api_client.dart';
import 'auth_provider.dart';

class HistoryState {
  final bool isLoading;
  final bool isExportingPdf;
  final List<Map<String, dynamic>> events;
  final String? nextCursor;
  final bool hasMore;
  final String? errorMessage;

  const HistoryState({
    this.isLoading = false,
    this.isExportingPdf = false,
    this.events = const [],
    this.nextCursor,
    this.hasMore = false,
    this.errorMessage,
  });

  HistoryState copyWith({
    bool? isLoading,
    bool? isExportingPdf,
    List<Map<String, dynamic>>? events,
    String? nextCursor,
    bool? hasMore,
    String? errorMessage,
  }) {
    return HistoryState(
      isLoading: isLoading ?? this.isLoading,
      isExportingPdf: isExportingPdf ?? this.isExportingPdf,
      events: events ?? this.events,
      nextCursor: nextCursor ?? this.nextCursor,
      hasMore: hasMore ?? this.hasMore,
      errorMessage: errorMessage,
    );
  }
}

class HistoryNotifier extends StateNotifier<HistoryState> {
  final ApiClient _apiClient;

  HistoryNotifier({required ApiClient apiClient})
      : _apiClient = apiClient,
        super(const HistoryState(isLoading: true)) {
    loadInitialFeed();
  }

  Future<void> loadInitialFeed() async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final res = await _apiClient.getHistoryFeed(limit: 20);
      final rawEvents = (res['events'] as List? ?? [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();

      state = state.copyWith(
        isLoading: false,
        events: rawEvents,
        nextCursor: res['next_cursor'] as String?,
        hasMore: res['has_more'] as bool? ?? false,
        errorMessage: null,
      );
    } catch (e) {
      final msg = e is ApiException ? e.message : e.toString();
      state = state.copyWith(isLoading: false, errorMessage: msg);
    }
  }

  Future<void> loadMore() async {
    if (state.isLoading || !state.hasMore || state.nextCursor == null) return;

    try {
      final res = await _apiClient.getHistoryFeed(
        before: state.nextCursor,
        limit: 20,
      );
      final newEvents = (res['events'] as List? ?? [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();

      state = state.copyWith(
        events: [...state.events, ...newEvents],
        nextCursor: res['next_cursor'] as String?,
        hasMore: res['has_more'] as bool? ?? false,
      );
    } catch (e) {
      // error loading more
    }
  }

  Future<List<int>?> exportPdf() async {
    state = state.copyWith(isExportingPdf: true, errorMessage: null);
    try {
      final bytes = await _apiClient.exportHistoryPdf();
      state = state.copyWith(isExportingPdf: false);
      return bytes;
    } catch (e) {
      final msg = e is ApiException ? e.message : e.toString();
      state = state.copyWith(isExportingPdf: false, errorMessage: msg);
      return null;
    }
  }
}

final historyProvider = StateNotifierProvider<HistoryNotifier, HistoryState>((ref) {
  final client = ref.watch(apiClientProvider);
  return HistoryNotifier(apiClient: client);
});
