/// Offline local cache and write-queue using Hive / in-memory fallback.
///
/// Ensures the user can view active medications, dose schedules, and recent alerts
/// even without network connectivity. Queues offline dose logs and alert acknowledgements
/// to be replayed automatically when internet connection is restored.
library;

import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:hive_flutter/hive_flutter.dart';

class OfflineWriteAction {
  final String actionType; // 'log_dose' | 'acknowledge_alert'
  final Map<String, dynamic> payload;
  final String queuedAt;

  OfflineWriteAction({
    required this.actionType,
    required this.payload,
    required this.queuedAt,
  });

  Map<String, dynamic> toJson() => {
    'actionType': actionType,
    'payload': payload,
    'queuedAt': queuedAt,
  };

  factory OfflineWriteAction.fromJson(Map<String, dynamic> json) =>
      OfflineWriteAction(
        actionType: json['actionType'] as String,
        payload: Map<String, dynamic>.from(json['payload'] as Map),
        queuedAt: json['queuedAt'] as String,
      );
}

class LocalCacheService {
  static const String _kMedicationsBox = 'cascadex_medications';
  static const String _kAlertsBox = 'cascadex_alerts';
  static const String _kHistoryBox = 'cascadex_history';
  static const String _kWriteQueueBox = 'cascadex_write_queue';

  bool _isInitialized = false;

  // In-memory fallbacks for unit tests or environments before Hive.initFlutter()
  final Map<String, dynamic> _memMedications = {};
  final Map<String, dynamic> _memAlerts = {};
  final List<OfflineWriteAction> _memWriteQueue = [];

  Future<void> init() async {
    if (_isInitialized) return;
    try {
      await Hive.initFlutter();
      await Hive.openBox(_kMedicationsBox);
      await Hive.openBox(_kAlertsBox);
      await Hive.openBox(_kHistoryBox);
      await Hive.openBox(_kWriteQueueBox);
      _isInitialized = true;
    } catch (e) {
      debugPrint('LocalCacheService: Hive initialization fallback to in-memory: $e');
      _isInitialized = true;
    }
  }

  // ---------------------------------------------------------------------------
  // Medications Cache
  // ---------------------------------------------------------------------------

  Future<void> cacheMedications(String userId, List<Map<String, dynamic>> medications) async {
    if (Hive.isBoxOpen(_kMedicationsBox)) {
      final box = Hive.box(_kMedicationsBox);
      await box.put(userId, jsonEncode(medications));
    } else {
      _memMedications[userId] = medications;
    }
  }

  Future<List<Map<String, dynamic>>> getCachedMedications(String userId) async {
    if (Hive.isBoxOpen(_kMedicationsBox)) {
      final box = Hive.box(_kMedicationsBox);
      final raw = box.get(userId);
      if (raw is String) {
        final decoded = jsonDecode(raw) as List;
        return decoded.map((e) => Map<String, dynamic>.from(e as Map)).toList();
      }
    }
    final mem = _memMedications[userId];
    if (mem is List) {
      return (mem).map((e) => Map<String, dynamic>.from(e as Map)).toList();
    }
    return [];
  }

  // ---------------------------------------------------------------------------
  // Alerts Cache
  // ---------------------------------------------------------------------------

  Future<void> cacheAlerts(String userId, List<Map<String, dynamic>> alerts) async {
    if (Hive.isBoxOpen(_kAlertsBox)) {
      final box = Hive.box(_kAlertsBox);
      await box.put(userId, jsonEncode(alerts));
    } else {
      _memAlerts[userId] = alerts;
    }
  }

  Future<List<Map<String, dynamic>>> getCachedAlerts(String userId) async {
    if (Hive.isBoxOpen(_kAlertsBox)) {
      final box = Hive.box(_kAlertsBox);
      final raw = box.get(userId);
      if (raw is String) {
        final decoded = jsonDecode(raw) as List;
        return decoded.map((e) => Map<String, dynamic>.from(e as Map)).toList();
      }
    }
    final mem = _memAlerts[userId];
    if (mem is List) {
      return (mem).map((e) => Map<String, dynamic>.from(e as Map)).toList();
    }
    return [];
  }

  // ---------------------------------------------------------------------------
  // Write Queue (Offline Replay)
  // ---------------------------------------------------------------------------

  Future<void> queueWriteAction(OfflineWriteAction action) async {
    if (Hive.isBoxOpen(_kWriteQueueBox)) {
      final box = Hive.box(_kWriteQueueBox);
      final queue = await getWriteQueue();
      queue.add(action);
      await box.put('queue', jsonEncode(queue.map((a) => a.toJson()).toList()));
    } else {
      _memWriteQueue.add(action);
    }
  }

  Future<List<OfflineWriteAction>> getWriteQueue() async {
    if (Hive.isBoxOpen(_kWriteQueueBox)) {
      final box = Hive.box(_kWriteQueueBox);
      final raw = box.get('queue');
      if (raw is String) {
        final decoded = jsonDecode(raw) as List;
        return decoded
            .map((e) => OfflineWriteAction.fromJson(Map<String, dynamic>.from(e as Map)))
            .toList();
      }
    }
    return List.from(_memWriteQueue);
  }

  Future<void> clearWriteQueue() async {
    if (Hive.isBoxOpen(_kWriteQueueBox)) {
      final box = Hive.box(_kWriteQueueBox);
      await box.delete('queue');
    }
    _memWriteQueue.clear();
  }
}
