/// Phase 08 — Main Application Widget Tests.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:cascadex/main.dart';
import 'package:cascadex/screens/onboarding_screen.dart';

void main() {
  group('CascadeX App Bootstrap & Routing', () {
    testWidgets('app boots with ProviderScope without throwing', (WidgetTester tester) async {
      await tester.pumpWidget(const ProviderScope(child: CascadeXApp()));
      await tester.pump(const Duration(milliseconds: 200));
      expect(tester.takeException(), isNull);
    });

    testWidgets('unauthenticated user is directed to OnboardingScreen', (WidgetTester tester) async {
      await tester.pumpWidget(const ProviderScope(child: CascadeXApp()));
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.byType(OnboardingScreen), findsOneWidget);
      expect(find.text('CascadeX — Safety Portal'), findsOneWidget);
      expect(find.text('Sign In'), findsOneWidget);
      expect(find.text('Create Account'), findsOneWidget);
    });
  });
}
