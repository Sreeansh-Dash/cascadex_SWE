/// Phase 08 — Accessibility & WCAG Compliance Widget Tests.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:cascadex/widgets/accessible_text.dart';
import 'package:cascadex/widgets/big_button.dart';
import 'package:cascadex/widgets/disclaimer_banner.dart';
import 'package:cascadex/widgets/severity_badge.dart';

void main() {
  group('Accessibility & Target Size Invariants', () {
    testWidgets('BigButton meets minimum 48x48dp touch target constraint',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: BigButton(
              text: 'Take Medication',
              onPressed: () {},
            ),
          ),
        ),
      );

      final buttonFinder = find.byType(BigButton);
      final size = tester.getSize(buttonFinder);

      expect(size.height, greaterThanOrEqualTo(48.0));
      expect(size.width, greaterThanOrEqualTo(48.0));
    });

    testWidgets('AccessibleText enforces 16sp floor even when 12sp requested',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AccessibleText(
              'Important Patient Instruction',
              style: TextStyle(fontSize: 12.0),
            ),
          ),
        ),
      );

      final textWidget = tester.widget<Text>(find.byType(Text));
      expect(textWidget.style?.fontSize, greaterThanOrEqualTo(16.0));
    });

    testWidgets('SeverityBadge provides spoken Semantics and icon (never color alone)',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: SeverityBadge(rawSeverity: 'major'),
          ),
        ),
      );

      // Verify explicit text label
      expect(find.text('MAJOR INTERACTION'), findsOneWidget);

      // Verify icon exists
      expect(find.byIcon(Icons.dangerous_rounded), findsOneWidget);

      // Verify Semantics label is present
      expect(
        find.bySemanticsLabel(RegExp(r'Major drug interaction detected')),
        findsOneWidget,
      );
    });

    testWidgets('DisclaimerBanner contains alert icon and safety disclaimer text',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: DisclaimerBanner(),
          ),
        ),
      );

      expect(find.byIcon(Icons.warning_amber_rounded), findsOneWidget);
      expect(find.textContaining('CascadeX is an academic software demonstration'), findsOneWidget);
    });
  });
}
