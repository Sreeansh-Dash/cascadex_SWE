/// Phase 01 — Flutter widget tests.
///
/// Tests:
/// - The app boots without throwing.
/// - The onboarding screen renders with the correct AppBar title.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:cascadex/main.dart';

void main() {
  group('Phase 01 — Onboarding screen', () {
    testWidgets('app boots without throwing', (WidgetTester tester) async {
      await tester.pumpWidget(const CascadeXApp());
      expect(tester.takeException(), isNull);
    });

    testWidgets('onboarding screen renders AppBar title', (WidgetTester tester) async {
      await tester.pumpWidget(const CascadeXApp());

      // Verify the onboarding AppBar title is visible.
      expect(find.text('CascadeX — Onboarding'), findsOneWidget);
    });

    testWidgets('onboarding screen shows phase placeholder text', (WidgetTester tester) async {
      await tester.pumpWidget(const CascadeXApp());

      // Verify the placeholder copy is present.
      expect(find.text('Phase 03 builds this screen'), findsOneWidget);
    });
  });
}
