/// Notification Service — in-app notifications and dose reminder management.
library;

import 'dart:async';
import 'package:flutter/foundation.dart';
import 'api_client.dart';

class NotificationService {
  final ApiClient _apiClient;
  Timer? _pollTimer;

  final ValueNotifier<int> unacknowledgedAlertCount = ValueNotifier<int>(0);
  final ValueNotifier<List<Map<String, dynamic>>> recentNotifications =
      ValueNotifier<List<Map<String, dynamic>>>([]);

  NotificationService({ApiClient? apiClient})
      : _apiClient = apiClient ?? ApiClient();

  void startPolling({Duration interval = const Duration(seconds: 30)}) {
    stopPolling();
    _pollTimer = Timer.periodic(interval, (_) => checkAlerts());
    checkAlerts();
  }

  void stopPolling() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  Future<void> checkAlerts() async {
    try {
      final alerts = await _apiClient.listAlerts(acknowledged: false);
      unacknowledgedAlertCount.value = alerts.length;
      recentNotifications.value = alerts;
    } catch (e) {
      debugPrint('Notification check failed (likely offline): $e');
    }
  }

  void dispose() {
    stopPolling();
    unacknowledgedAlertCount.dispose();
    recentNotifications.dispose();
  }
}
