/// Phase 08 — MedicationListScreen Widget Tests.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:cascadex/screens/medication_list_screen.dart';
import 'package:cascadex/state/alert_provider.dart';
import 'package:cascadex/state/medication_provider.dart';
import 'package:cascadex/widgets/severity_badge.dart';

class MockMedicationNotifier extends StateNotifier<MedicationState>
    implements MedicationNotifier {
  MockMedicationNotifier(super.state);

  @override
  Future<void> loadMedications() async {
    // Keep loaded state
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class MockAlertNotifier extends StateNotifier<AlertState>
    implements AlertNotifier {
  MockAlertNotifier(super.state);

  @override
  Future<void> loadAlerts() async {
    // Keep loaded state
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  testWidgets('renders active medications with severity badges and dose action buttons',
      (WidgetTester tester) async {
    final testMeds = [
      {
        'entry_id': 'med_001',
        'generic_name': 'warfarin',
        'drug_class': 'Anticoagulant',
        'dosage_amount': 5.0,
        'dosage_unit': 'mg',
        'is_active': true,
        'schedules': [
          {'time_of_day': '08:00', 'days_of_week': []}
        ],
      },
      {
        'entry_id': 'med_002',
        'generic_name': 'aspirin',
        'drug_class': 'NSAID',
        'dosage_amount': 81.0,
        'dosage_unit': 'mg',
        'is_active': true,
        'schedules': [
          {'time_of_day': '12:00', 'days_of_week': []}
        ],
      },
    ];

    final testAlerts = [
      {
        'alert_id': 'alert_001',
        'entry_a_id': 'med_001',
        'entry_b_id': 'med_002',
        'drug_a_name': 'warfarin',
        'drug_b_name': 'aspirin',
        'severity_at_trigger': 'major',
        'requires_acknowledgment': true,
        'acknowledged': false,
      }
    ];

    final medNotifier = MockMedicationNotifier(
      MedicationState(
        isLoading: false,
        medications: testMeds,
      ),
    );

    final alertNotifier = MockAlertNotifier(
      AlertState(
        isLoading: false,
        alerts: testAlerts,
      ),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          medicationProvider.overrideWith((ref) => medNotifier),
          alertProvider.overrideWith((ref) => alertNotifier),
        ],
        child: const MaterialApp(
          home: MedicationListScreen(),
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Verify both medication names are rendered in the list
    expect(find.text('WARFARIN'), findsOneWidget);
    expect(find.text('ASPIRIN'), findsOneWidget);

    // Verify dosages
    expect(find.text('5.0 mg'), findsOneWidget);
    expect(find.text('81.0 mg'), findsOneWidget);

    // Verify SeverityBadge is rendered
    expect(find.byType(SeverityBadge), findsWidgets);
    expect(find.text('MAJOR INTERACTION'), findsWidgets);

    // Verify Quick Action Dose Logging Buttons
    expect(find.text('Log Taken'), findsNWidgets(2));
    expect(find.text('Skip'), findsNWidgets(2));
  });
}
