/// CascadeX Flutter application entry point.
///
/// Wires up named routes to the 7 placeholder screens defined in Phase 01.
/// Business logic, state management (Riverpod), and real UI are
/// implemented in Phases 03–08.
///
/// ⚠️ Medical disclaimer: CascadeX is a course demonstration project and
/// does not replace a pharmacist or doctor.
library;

import 'package:flutter/material.dart';
import 'screens/onboarding_screen.dart';
import 'screens/medication_list_screen.dart';
import 'screens/add_medication_screen.dart';
import 'screens/scan_screen.dart';
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
      routes: {
        '/onboarding': (_) => const OnboardingScreen(),
        '/medications': (_) => const MedicationListScreen(),
        '/medications/add': (_) => const AddMedicationScreen(),
        '/scan': (_) => const ScanScreen(),
        '/alerts/detail': (_) => const AlertDetailScreen(),
        '/history': (_) => const HistoryScreen(),
        '/settings': (_) => const SettingsScreen(),
      },
    );
  }
}
