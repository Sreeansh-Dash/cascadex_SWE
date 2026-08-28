/// SettingsScreen — Accessibility, Caregiver Management, and System Settings.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../state/auth_provider.dart';
import '../state/settings_provider.dart';
import '../theme/colors.dart';
import '../theme/typography.dart';
import '../widgets/big_button.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  final _caregiverEmailController = TextEditingController();
  final _relationshipController = TextEditingController();
  String _permissionLevel = 'view_only'; // 'view_only' | 'manage'

  @override
  void dispose() {
    _caregiverEmailController.dispose();
    _relationshipController.dispose();
    super.dispose();
  }

  Future<void> _handleLinkCaregiver() async {
    final email = _caregiverEmailController.text.trim();
    if (email.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter caregiver email or phone')),
      );
      return;
    }

    final success = await ref.read(settingsProvider.notifier).linkCaregiver(
          emailOrPhone: email,
          permissionLevel: _permissionLevel,
          relationship: _relationshipController.text.trim().isNotEmpty
              ? _relationshipController.text.trim()
              : null,
        );

    if (success && mounted) {
      _caregiverEmailController.clear();
      _relationshipController.clear();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Caregiver linked successfully!')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final settings = ref.watch(settingsProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Settings & Safety', style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            // 1. Accessibility Font Scale Section
            Text('ACCESSIBILITY & DISPLAY', style: AppText.caption.copyWith(fontWeight: FontWeight.bold, color: AppColors.primaryDark)),
            const SizedBox(height: 8),
            Card(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Text Size Multiplier', style: AppText.subhead),
                    const SizedBox(height: 4),
                    const Text('Scales all app text for improved readability', style: AppText.caption),
                    const SizedBox(height: 12),
                    SegmentedButton<double>(
                      segments: const [
                        ButtonSegment(value: 1.0, label: Text('Normal (1.0x)')),
                        ButtonSegment(value: 1.25, label: Text('Large (1.25x)')),
                        ButtonSegment(value: 1.5, label: Text('XL (1.5x)')),
                      ],
                      selected: {settings.fontScale},
                      onSelectionChanged: (set) => ref.read(settingsProvider.notifier).setFontScale(set.first),
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 24),

            // 2. Caregiver Management Section
            Text('CAREGIVER PERMISSIONS (RBAC)', style: AppText.caption.copyWith(fontWeight: FontWeight.bold, color: AppColors.primaryDark)),
            const SizedBox(height: 8),
            Card(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Link a Trusted Caregiver', style: AppText.subhead),
                    const SizedBox(height: 4),
                    const Text(
                      'Allow family members or nurses to view or manage your medications.',
                      style: AppText.caption,
                    ),
                    const SizedBox(height: 14),
                    TextField(
                      controller: _caregiverEmailController,
                      decoration: const InputDecoration(
                        labelText: 'Caregiver Email or Phone',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.person_add_outlined),
                      ),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: _relationshipController,
                      decoration: const InputDecoration(
                        labelText: 'Relationship (e.g. Daughter, Nurse)',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.family_restroom),
                      ),
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      value: _permissionLevel,
                      decoration: const InputDecoration(
                        labelText: 'Access Level',
                        border: OutlineInputBorder(),
                      ),
                      items: const [
                        DropdownMenuItem(
                          value: 'view_only',
                          child: Text('View Only (Read-Only Access)'),
                        ),
                        DropdownMenuItem(
                          value: 'manage',
                          child: Text('Manage (Can Add Meds & Acknowledge)'),
                        ),
                      ],
                      onChanged: (v) {
                        if (v != null) setState(() => _permissionLevel = v);
                      },
                    ),
                    const SizedBox(height: 16),
                    BigButton(
                      text: 'Grant Access',
                      isLoading: settings.isLoading,
                      onPressed: _handleLinkCaregiver,
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 24),

            // 3. About & Clinical Sources
            Text('CLINICAL KNOWLEDGEBASE', style: AppText.caption.copyWith(fontWeight: FontWeight.bold, color: AppColors.primaryDark)),
            const SizedBox(height: 8),
            Card(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              child: ListTile(
                leading: const Icon(Icons.info_outline, color: AppColors.primary, size: 28),
                title: const Text('About Safety Data & Attributions', style: AppText.subhead),
                subtitle: const Text('DDInter 2.0 & NLM RxNorm versioning details'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => context.push('/about'),
              ),
            ),

            const SizedBox(height: 28),

            // 4. Sign Out Button
            BigButton(
              text: 'Sign Out',
              isSecondary: true,
              textColor: AppColors.error,
              onPressed: () async {
                final nav = GoRouter.of(context);
                await ref.read(authProvider.notifier).logout();
                if (mounted) nav.go('/onboarding');
              },
            ),

            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }
}
