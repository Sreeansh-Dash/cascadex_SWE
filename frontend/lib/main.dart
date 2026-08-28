/// CascadeX Flutter Application Entry Point — Phase 08.
///
/// Features:
/// - Riverpod ProviderScope at root
/// - GoRouter with auth-state redirection
/// - WCAG AA accessible Theme & Typography
/// - Dynamic text scaling provider integration
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'screens/about_data_screen.dart';
import 'screens/add_medication_screen.dart';
import 'screens/alert_detail_screen.dart';
import 'screens/history_screen.dart';
import 'screens/medication_list_screen.dart';
import 'screens/onboarding_screen.dart';
import 'screens/scan_confirmation_screen.dart';
import 'screens/scan_screen.dart';
import 'screens/settings_screen.dart';
import 'services/ocr_service.dart';
import 'state/auth_provider.dart';
import 'state/settings_provider.dart';
import 'theme/colors.dart';
import 'theme/typography.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ProviderScope(child: CascadeXApp()));
}

final routerProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    initialLocation: '/onboarding',
    redirect: (context, state) {
      if (authState.isLoading) return null;

      final isLoggingIn = state.matchedLocation == '/onboarding';

      if (!authState.isAuthenticated) {
        return isLoggingIn ? null : '/onboarding';
      }

      if (isLoggingIn) {
        return '/medications';
      }

      return null;
    },
    routes: [
      GoRoute(
        path: '/onboarding',
        builder: (context, state) => const OnboardingScreen(),
      ),
      GoRoute(
        path: '/medications',
        builder: (context, state) => const MedicationListScreen(),
      ),
      GoRoute(
        path: '/medications/add',
        builder: (context, state) {
          final prefilled = state.extra as Map<String, dynamic>?;
          return AddMedicationScreen(prefilledDrug: prefilled);
        },
      ),
      GoRoute(
        path: '/scan',
        builder: (context, state) {
          final auth = ref.read(authProvider);
          return ScanScreen(accessToken: auth.userId ?? '');
        },
      ),
      GoRoute(
        path: '/scan/confirm',
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>? ?? {};
          final scanResult = extra['scanResult'] as OcrScanResult;
          final token = extra['accessToken'] as String? ?? '';
          return ScanConfirmationScreen(
            scanResult: scanResult,
            accessToken: token,
          );
        },
      ),
      GoRoute(
        path: '/alerts/detail',
        builder: (context, state) {
          final alert = state.extra as Map<String, dynamic>? ?? {};
          return AlertDetailScreen(alert: alert);
        },
      ),
      GoRoute(
        path: '/history',
        builder: (context, state) => const HistoryScreen(),
      ),
      GoRoute(
        path: '/settings',
        builder: (context, state) => const SettingsScreen(),
      ),
      GoRoute(
        path: '/about',
        builder: (context, state) => const AboutDataScreen(),
      ),
    ],
  );
});

class CascadeXApp extends ConsumerWidget {
  const CascadeXApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    final settings = ref.watch(settingsProvider);

    return MaterialApp.router(
      title: 'CascadeX',
      debugShowCheckedModeBanner: false,
      routerConfig: router,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: AppColors.lightColorScheme,
        textTheme: AppText.textTheme,
        scaffoldBackgroundColor: AppColors.background,
        appBarTheme: const AppBarTheme(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          elevation: 0,
        ),
      ),
      builder: (context, child) {
        return MediaQuery(
          data: MediaQuery.of(context).copyWith(
            textScaler: TextScaler.linear(settings.fontScale),
          ),
          child: child ?? const SizedBox.shrink(),
        );
      },
    );
  }
}
