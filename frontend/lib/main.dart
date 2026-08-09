/// CascadeX Flutter application entry point.
///
/// Wires up named routes to the 7 placeholder screens defined in Phase 01.
/// Phase 05 adds ScanScreen (camera + OCR) and ScanConfirmationScreen.
/// Phase 08 replaces this with a Riverpod-scoped app and GoRouter with
/// proper auth-gated routing.
///
/// ⚠️ Medical disclaimer: CascadeX is a course demonstration project and
/// does not replace a pharmacist or doctor.
library;

import 'package:flutter/material.dart';
import 'screens/onboarding_screen.dart';
import 'screens/medication_list_screen.dart';
import 'screens/add_medication_screen.dart';
import 'screens/scan_screen.dart';
import 'screens/scan_confirmation_screen.dart';
import 'screens/alert_detail_screen.dart';
import 'screens/history_screen.dart';
import 'screens/settings_screen.dart';

void main() {
  runApp(const CascadeXApp());
}

/// Root application widget.
///
/// Uses [MaterialApp] with named routes for navigation.
/// Phase 08 replaces this with a Riverpod-scoped app and GoRouter.
class CascadeXApp extends StatelessWidget {
  const CascadeXApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CascadeX',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1A73E8),
          brightness: Brightness.light,
        ),
        // Phase 08 replaces this with the full custom design system
        // (colors.dart + typography.dart tokens).
      ),
      // Named route table — every screen in the app is registered here.
      initialRoute: '/onboarding',
      onGenerateRoute: (settings) {
        // Extract accessToken from route arguments (set by auth flow).
        // Defaults to '' for Phase 01 scaffold; Phase 08 wires real token.
        final token = settings.arguments is Map<String, dynamic>
            ? (settings.arguments as Map<String, dynamic>)['accessToken'] as String? ?? ''
            : '';

        switch (settings.name) {
          case '/onboarding':
            return MaterialPageRoute(builder: (_) => const OnboardingScreen());
          case '/medications':
            return MaterialPageRoute(builder: (_) => const MedicationListScreen());
          case '/medications/add':
            return MaterialPageRoute(builder: (_) => const AddMedicationScreen());
          case '/scan':
            return MaterialPageRoute(
              builder: (_) => ScanScreen(accessToken: token),
            );
          case '/alerts/detail':
            return MaterialPageRoute(builder: (_) => const AlertDetailScreen());
          case '/history':
            return MaterialPageRoute(builder: (_) => const HistoryScreen());
          case '/settings':
            return MaterialPageRoute(builder: (_) => const SettingsScreen());
          default:
            return MaterialPageRoute(builder: (_) => const OnboardingScreen());
        }
      },
    );
  }
}
