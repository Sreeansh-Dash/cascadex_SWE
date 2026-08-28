/// Phase 08 — Local Cache & Offline Queue Unit Tests.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:cascadex/services/local_cache.dart';

void main() {
  group('LocalCacheService & Offline Write Queue', () {
    late LocalCacheService cache;

    setUp(() {
      cache = LocalCacheService();
    });

    test('caches and retrieves medications for a user', () async {
      final testMeds = [
        {
          'entry_id': 'med_101',
          'generic_name': 'metformin',
          'dosage_amount': 500.0,
          'dosage_unit': 'mg',
          'is_active': true,
        }
      ];

      await cache.cacheMedications('user_123', testMeds);
      final retrieved = await cache.getCachedMedications('user_123');

      expect(retrieved.length, equals(1));
      expect(retrieved.first['generic_name'], equals('metformin'));
    });

    test('caches and retrieves alerts for a user', () async {
      final testAlerts = [
        {
          'alert_id': 'alert_999',
          'drug_a_name': 'warfarin',
          'drug_b_name': 'aspirin',
          'severity_at_trigger': 'major',
        }
      ];

      await cache.cacheAlerts('user_123', testAlerts);
      final retrieved = await cache.getCachedAlerts('user_123');

      expect(retrieved.length, equals(1));
      expect(retrieved.first['alert_id'], equals('alert_999'));
    });

    test('queues offline dose log and clears queue', () async {
      final action = OfflineWriteAction(
        actionType: 'log_dose',
        payload: {
          'entry_id': 'med_101',
          'status': 'taken',
          'scheduled_time': '2026-08-27T08:00:00Z',
        },
        queuedAt: '2026-08-27T08:05:00Z',
      );

      await cache.queueWriteAction(action);
      var queue = await cache.getWriteQueue();

      expect(queue.length, equals(1));
      expect(queue.first.actionType, equals('log_dose'));
      expect(queue.first.payload['entry_id'], equals('med_101'));

      await cache.clearWriteQueue();
      queue = await cache.getWriteQueue();
      expect(queue.isEmpty, isTrue);
    });
  });
}
