/// AlertsScreen — Lists all interaction alerts for the signed-in user.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../state/alert_provider.dart';
import '../theme/colors.dart';
import '../theme/typography.dart';
import '../widgets/disclaimer_banner.dart';
import '../widgets/severity_badge.dart';

class AlertsScreen extends ConsumerStatefulWidget {
  const AlertsScreen({super.key});

  @override
  ConsumerState<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends ConsumerState<AlertsScreen> {
  @override
  Widget build(BuildContext context) {
    final alertState = ref.watch(alertProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Safety Alerts',
            style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
      ),
      body: SafeArea(
        child: Column(
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 12, 16, 4),
              child: DisclaimerBanner(isCompact: true),
            ),
            Expanded(
              child: alertState.isLoading && alertState.alerts.isEmpty
                  ? const Center(child: CircularProgressIndicator())
                  : RefreshIndicator(
                      onRefresh: () =>
                          ref.read(alertProvider.notifier).loadAlerts(),
                      child: alertState.alerts.isEmpty
                          ? ListView(
                              children: const [
                                SizedBox(height: 80),
                                Center(
                                    child: Text(
                                        'No safety alerts recorded yet.',
                                        style: AppText.body)),
                              ],
                            )
                          : ListView.builder(
                              padding: const EdgeInsets.all(16),
                              itemCount: alertState.alerts.length,
                              itemBuilder: (context, index) {
                                final alert = alertState.alerts[index];
                                return _buildAlertCard(context, alert);
                              },
                            ),
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAlertCard(BuildContext context, Map<String, dynamic> alert) {
    final severity = alert['severity_at_trigger'] as String? ?? 'major';
    final acknowledged = alert['acknowledged'] as bool? ?? false;
    final drugA = (alert['drug_a_name'] as String? ?? 'Drug A').toUpperCase();
    final drugB = (alert['drug_b_name'] as String? ?? 'Drug B').toUpperCase();
    final triggeredAt = alert['triggered_at'] as String? ?? '';
    final date =
        triggeredAt.length >= 10 ? triggeredAt.substring(0, 10) : triggeredAt;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 1.5,
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        leading: Icon(
          acknowledged ? Icons.check_circle_outline : Icons.warning_rounded,
          color: acknowledged ? AppColors.success : AppColors.severityMajor,
          size: 32,
        ),
        title: Text('$drugA + $drugB',
            style: const TextStyle(fontWeight: FontWeight.bold)),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Row(
            children: [
              SeverityBadge(rawSeverity: severity),
              const SizedBox(width: 8),
              Text(acknowledged ? 'Reviewed' : 'Needs review'),
              if (date.isNotEmpty) ...[
                const SizedBox(width: 8),
                Text(date),
              ],
            ],
          ),
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: () => context.push('/alerts/detail', extra: alert),
      ),
    );
  }
}
