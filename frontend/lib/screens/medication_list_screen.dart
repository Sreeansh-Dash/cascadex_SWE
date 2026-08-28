/// MedicationListScreen — Primary Medication Management Dashboard.
///
/// Features:
/// - Active & Inactive medication list with high-contrast accessible cards
/// - Inline Severity Badges for active interactions
/// - Rapid 1-tap dose logging ("Taken" / "Skipped") directly on medication card (<= 3 taps total)
/// - Single-tap Add Medication button (<= 3 taps to add)
/// - Offline mode banner with cached data indicator
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../state/alert_provider.dart';
import '../state/medication_provider.dart';
import '../theme/colors.dart';
import '../theme/typography.dart';
import '../widgets/accessible_text.dart';
import '../widgets/disclaimer_banner.dart';
import '../widgets/offline_banner.dart';
import '../widgets/severity_badge.dart';

class MedicationListScreen extends ConsumerStatefulWidget {
  const MedicationListScreen({super.key});

  @override
  ConsumerState<MedicationListScreen> createState() => _MedicationListScreenState();
}

class _MedicationListScreenState extends ConsumerState<MedicationListScreen> {
  bool _showInactive = false;

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      ref.read(medicationProvider.notifier).loadMedications();
      ref.read(alertProvider.notifier).loadAlerts();
    });
  }

  Future<void> _handleLogDose(String entryId, String status) async {
    final nowIso = DateTime.now().toIso8601String();
    await ref.read(medicationProvider.notifier).logDose(
          entryId: entryId,
          status: status,
          scheduledTime: nowIso,
          takenAt: status == 'taken' ? nowIso : null,
        );

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(status == 'taken' ? 'Dose logged as TAKEN ✅' : 'Dose logged as SKIPPED ⏸️'),
          duration: const Duration(seconds: 2),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final medState = ref.watch(medicationProvider);
    final alertState = ref.watch(alertProvider);
    final unackedAlerts = alertState.unacknowledgedAlerts;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('My Medications', style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        elevation: 0,
        actions: [
          IconButton(
            icon: Stack(
              children: [
                const Icon(Icons.notifications_outlined, size: 28),
                if (unackedAlerts.isNotEmpty)
                  Positioned(
                    right: 0,
                    top: 0,
                    child: Container(
                      padding: const EdgeInsets.all(4),
                      decoration: const BoxDecoration(
                        color: AppColors.severityMajor,
                        shape: BoxShape.circle,
                      ),
                      child: Text(
                        '${unackedAlerts.length}',
                        style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ),
              ],
            ),
            tooltip: 'View Alerts (${unackedAlerts.length} active)',
            onPressed: () {
              if (unackedAlerts.isNotEmpty) {
                final firstAlert = unackedAlerts.first;
                context.push('/alerts/detail', extra: firstAlert);
              } else {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('No active unacknowledged alerts')),
                );
              }
            },
          ),
          IconButton(
            icon: const Icon(Icons.history_outlined, size: 28),
            tooltip: 'Dose History Timeline',
            onPressed: () => context.push('/history'),
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined, size: 28),
            tooltip: 'Settings & Profile',
            onPressed: () => context.push('/settings'),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push('/medications/add'),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.add, size: 26),
        label: const Text('Add Medication', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
      ),
      body: SafeArea(
        child: Column(
          children: [
            if (medState.isOffline)
              OfflineBanner(
                onRetry: () => ref.read(medicationProvider.notifier).loadMedications(),
              ),

            // Top Alert Notice Bar if major unacknowledged alerts exist
            if (unackedAlerts.isNotEmpty)
              InkWell(
                onTap: () => context.push('/alerts/detail', extra: unackedAlerts.first),
                child: Container(
                  width: double.infinity,
                  color: AppColors.severityMajorBg,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                  child: Row(
                    children: [
                      const Icon(Icons.warning_rounded, color: AppColors.severityMajor, size: 24),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          '${unackedAlerts.length} safety alert(s) require review',
                          style: const TextStyle(
                            color: AppColors.severityMajor,
                            fontSize: 15,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      const Text(
                        'REVIEW',
                        style: TextStyle(
                          color: AppColors.severityMajor,
                          fontWeight: FontWeight.bold,
                          decoration: TextDecoration.underline,
                        ),
                      ),
                    ],
                  ),
                ),
              ),

            Expanded(
              child: medState.isLoading && medState.medications.isEmpty
                  ? const Center(child: CircularProgressIndicator())
                  : RefreshIndicator(
                      onRefresh: () async {
                        await ref.read(medicationProvider.notifier).loadMedications();
                        await ref.read(alertProvider.notifier).loadAlerts();
                      },
                      child: ListView(
                        padding: const EdgeInsets.all(16),
                        children: [
                          const DisclaimerBanner(isCompact: true),
                          const SizedBox(height: 16),

                          // Active Medications Section
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                'ACTIVE REGIMEN (${medState.activeMedications.length})',
                                style: AppText.caption.copyWith(
                                  fontWeight: FontWeight.bold,
                                  letterSpacing: 0.8,
                                  color: AppColors.primaryDark,
                                ),
                              ),
                              TextButton.icon(
                                onPressed: () => context.push('/scan'),
                                icon: const Icon(Icons.camera_alt_outlined, size: 18),
                                label: const Text('Scan Bottle'),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),

                          if (medState.activeMedications.isEmpty)
                            _buildEmptyState()
                          else
                            ...medState.activeMedications.map(
                              (med) => _buildMedicationCard(med, alertState.alerts),
                            ),

                          const SizedBox(height: 24),

                          // Inactive Medications Expansion
                          if (medState.inactiveMedications.isNotEmpty) ...[
                            ListTile(
                              contentPadding: EdgeInsets.zero,
                              title: Text(
                                'Inactive / Past Medications (${medState.inactiveMedications.length})',
                                style: AppText.subhead.copyWith(color: AppColors.textMuted),
                              ),
                              trailing: Icon(
                                _showInactive ? Icons.expand_less : Icons.expand_more,
                                color: AppColors.textMuted,
                              ),
                              onTap: () => setState(() => _showInactive = !_showInactive),
                            ),
                            if (_showInactive)
                              ...medState.inactiveMedications.map(
                                (med) => _buildMedicationCard(med, [], isInactive: true),
                              ),
                          ],

                          const SizedBox(height: 80), // Padding for FAB
                        ],
                      ),
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Container(
      padding: const EdgeInsets.all(28),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.cardBorder),
      ),
      child: Column(
        children: [
          const Icon(Icons.medication_outlined, size: 64, color: AppColors.primary),
          const SizedBox(height: 12),
          const Text('No Active Medications', style: AppText.headline),
          const SizedBox(height: 6),
          const Text(
            'Add your prescribed medications to enable automated drug-drug interaction safety monitoring.',
            style: AppText.body,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 20),
          ElevatedButton.icon(
            onPressed: () => context.push('/medications/add'),
            icon: const Icon(Icons.add),
            label: const Text('Add First Medication'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMedicationCard(
    Map<String, dynamic> med,
    List<Map<String, dynamic>> allAlerts, {
    bool isInactive = false,
  }) {
    final entryId = med['entry_id'] as String;
    final genericName = (med['generic_name'] as String? ?? 'Medication').toUpperCase();
    final dosageAmount = med['dosage_amount'];
    final dosageUnit = med['dosage_unit'] ?? '';
    final drugClass = med['drug_class'] as String? ?? '';
    final schedules = (med['schedules'] as List? ?? []);

    // Check if this medication has active alerts
    Map<String, dynamic>? matchedAlert;
    for (final a in allAlerts) {
      final drugA = a['drug_a_name']?.toString().toLowerCase();
      final drugB = a['drug_b_name']?.toString().toLowerCase();
      final gName = genericName.toLowerCase();
      final eA = a['entry_a_id']?.toString();
      final eB = a['entry_b_id']?.toString();
      final ack = a['acknowledged'] == true;

      if (!ack && (eA == entryId || eB == entryId || drugA == gName || drugB == gName)) {
        matchedAlert = a;
        break;
      }
    }

    final String? severity = matchedAlert?['severity_at_trigger'] as String?;

    return Card(
      margin: const EdgeInsets.only(bottom: 14),
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(
          color: severity != null ? AppColors.severityMajor : AppColors.cardBorder,
          width: severity != null ? 1.5 : 1,
        ),
      ),
      color: isInactive ? const Color(0xFFFAFAFA) : Colors.white,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      AccessibleText(
                        genericName,
                        style: AppText.headline.copyWith(
                          fontSize: 19,
                          color: isInactive ? AppColors.textMuted : AppColors.textPrimary,
                        ),
                      ),
                      if (drugClass.isNotEmpty)
                        Text(
                          drugClass,
                          style: AppText.caption.copyWith(color: AppColors.primary),
                        ),
                    ],
                  ),
                ),
                if (severity != null)
                  InkWell(
                    onTap: () => context.push('/alerts/detail', extra: matchedAlert),
                    child: SeverityBadge(rawSeverity: severity, isCompact: true),
                  ),
              ],
            ),
            const SizedBox(height: 12),

            // Dosage & Schedule Details
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppColors.primaryLight,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.scale_outlined, size: 16, color: AppColors.primaryDark),
                      const SizedBox(width: 6),
                      Text(
                        '$dosageAmount $dosageUnit',
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.bold,
                          color: AppColors.primaryDark,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 10),
                if (schedules.isNotEmpty)
                  Expanded(
                    child: Text(
                      'Take at: ${schedules.map((s) => s['time_of_day']).join(', ')}',
                      style: AppText.caption,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
            ),

            if (!isInactive) ...[
              const Divider(height: 24),
              // Action Row (Dose Logging)
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  OutlinedButton.icon(
                    onPressed: () => _handleLogDose(entryId, 'skipped'),
                    icon: const Icon(Icons.pause_circle_outline, size: 18),
                    label: const Text('Skip'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.textSecondary,
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                    ),
                  ),
                  ElevatedButton.icon(
                    onPressed: () => _handleLogDose(entryId, 'taken'),
                    icon: const Icon(Icons.check_circle, size: 18),
                    label: const Text('Log Taken'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.success,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
