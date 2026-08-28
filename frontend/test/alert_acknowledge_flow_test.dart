/// Phase 08 — AlertDetailScreen & Acknowledgment Flow Widget Tests.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:cascadex/screens/alert_detail_screen.dart';
import 'package:cascadex/widgets/disclaimer_banner.dart';
import 'package:cascadex/widgets/severity_badge.dart';

void main() {
  group('Alert Detail & Acknowledgment Invariants', () {
    testWidgets('major alert shows mandatory acknowledgment button and disclaimer',
        (WidgetTester tester) async {
      final majorAlert = {
        'alert_id': 'alert_123',
        'drug_a_name': 'warfarin',
        'drug_b_name': 'aspirin',
        'severity_at_trigger': 'major',
        'requires_acknowledgment': true,
        'acknowledged': false,
        'plain_language': 'Taking warfarin with aspirin greatly increases severe bleeding risk.',
        'management_advice': 'Avoid co-administration or monitor closely.',
        'triggered_at': '2026-08-27T10:00:00Z',
      };

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: AlertDetailScreen(alert: majorAlert),
          ),
        ),
      );

      // Verify severity badge
      expect(find.byType(SeverityBadge), findsOneWidget);
      expect(find.text('MAJOR INTERACTION'), findsOneWidget);

      // Verify disclaimer banner is present
      expect(find.byType(DisclaimerBanner), findsOneWidget);

      // Verify explicit acknowledgment button is present for major
      expect(find.text('I Acknowledge This Warning'), findsOneWidget);
      expect(find.text('What You Need to Know'), findsOneWidget);
      expect(find.text('Clinical Guidance & Next Steps'), findsOneWidget);
    });

    testWidgets('already acknowledged alert shows acknowledged status banner',
        (WidgetTester tester) async {
      final ackAlert = {
        'alert_id': 'alert_456',
        'drug_a_name': 'lisinopril',
        'drug_b_name': 'metformin',
        'severity_at_trigger': 'minor',
        'requires_acknowledgment': false,
        'acknowledged': true,
        'plain_language': 'Slightly increased hypoglycemia risk.',
        'management_advice': 'Monitor blood glucose.',
        'triggered_at': '2026-08-27T10:00:00Z',
      };

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: AlertDetailScreen(alert: ackAlert),
          ),
        ),
      );

      expect(find.text('This warning has been acknowledged.'), findsOneWidget);
      expect(find.text('I Acknowledge This Warning'), findsNothing);
    });
  });
}
