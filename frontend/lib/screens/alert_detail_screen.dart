/// AlertDetailScreen — Comprehensive Interaction Warning & Acknowledgment Flow.
///
/// Safety Invariants:
/// - Severity 'major' requires explicit user acknowledgment.
/// - Mandatory safety disclaimer displayed prominently on all views.
/// - Full clinical management guidance provided from DDInter 2.0.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../state/alert_provider.dart';
import '../theme/colors.dart';
import '../theme/typography.dart';
import '../widgets/accessible_text.dart';
import '../widgets/big_button.dart';
import '../widgets/disclaimer_banner.dart';
import '../widgets/severity_badge.dart';

class AlertDetailScreen extends ConsumerStatefulWidget {
  final Map<String, dynamic> alert;

  const AlertDetailScreen({super.key, required this.alert});

  @override
  ConsumerState<AlertDetailScreen> createState() => _AlertDetailScreenState();
}

class _AlertDetailScreenState extends ConsumerState<AlertDetailScreen> {
  bool _isAcknowledging = false;
  late bool _acknowledged;

  @override
  void initState() {
    super.initState();
    _acknowledged = widget.alert['acknowledged'] as bool? ?? false;
  }

  Future<void> _handleAcknowledge() async {
    setState(() => _isAcknowledging = true);
    final alertId = widget.alert['alert_id'] as String;

    final success = await ref.read(alertProvider.notifier).acknowledgeAlert(alertId);

    if (mounted) {
      setState(() {
        _isAcknowledging = false;
        if (success) _acknowledged = true;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Warning acknowledged ✅'),
          backgroundColor: AppColors.success,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final alert = widget.alert;
    final drugA = (alert['drug_a_name'] as String? ?? 'Drug A').toUpperCase();
    final drugB = (alert['drug_b_name'] as String? ?? 'Drug B').toUpperCase();
    final severity = alert['severity_at_trigger'] as String? ?? 'major';
    final plainLanguage = alert['plain_language'] as String? ?? 'Potential interaction detected between these medications.';
    final management = alert['management_advice'] as String? ?? 'Consult your prescribing doctor or pharmacist.';
    final requiresAck = alert['requires_acknowledgment'] as bool? ?? (severity == 'major');
    final triggeredAt = alert['triggered_at'] as String? ?? '';

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Interaction Warning', style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: severity == 'major' ? AppColors.severityMajor : AppColors.primary,
        foregroundColor: Colors.white,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Disclaimer at top
              const DisclaimerBanner(),
              const SizedBox(height: 20),

              // Severity & Drug Header Card
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: severity == 'major' ? AppColors.severityMajor : AppColors.cardBorder,
                    width: severity == 'major' ? 2 : 1,
                  ),
                  boxShadow: const [
                    BoxShadow(color: Colors.black12, blurRadius: 6, offset: Offset(0, 2)),
                  ],
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    SeverityBadge(rawSeverity: severity),
                    const SizedBox(height: 16),
                    Text(
                      '$drugA + $drugB',
                      style: AppText.headline.copyWith(
                        fontSize: 22,
                        color: severity == 'major' ? AppColors.severityMajor : AppColors.textPrimary,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    if (triggeredAt.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Text(
                        'Detected: ${triggeredAt.length > 10 ? triggeredAt.substring(0, 10) : triggeredAt}',
                        style: AppText.caption,
                      ),
                    ],
                  ],
                ),
              ),

              const SizedBox(height: 20),

              // Plain Language Explanation
              _buildSectionCard(
                title: 'What You Need to Know',
                icon: Icons.article_outlined,
                content: plainLanguage,
              ),

              const SizedBox(height: 16),

              // Clinical Management Guidance
              _buildSectionCard(
                title: 'Clinical Guidance & Next Steps',
                icon: Icons.health_and_safety_outlined,
                content: management,
              ),

              const SizedBox(height: 28),

              // Acknowledgment Action Box
              if (_acknowledged)
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppColors.successBg,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.success),
                  ),
                  child: const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.check_circle, color: AppColors.success, size: 24),
                      SizedBox(width: 10),
                      Text(
                        'This warning has been acknowledged.',
                        style: TextStyle(
                          color: AppColors.success,
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                        ),
                      ),
                    ],
                  ),
                )
              else if (requiresAck)
                Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    BigButton(
                      text: 'I Acknowledge This Warning',
                      icon: Icons.check,
                      backgroundColor: AppColors.severityMajor,
                      isLoading: _isAcknowledging,
                      onPressed: _handleAcknowledge,
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Acknowledging confirms you have reviewed this warning and will discuss it with your pharmacist or doctor.',
                      style: AppText.caption,
                      textAlign: TextAlign.center,
                    ),
                  ],
                )
              else
                BigButton(
                  text: 'Mark as Reviewed',
                  isSecondary: true,
                  isLoading: _isAcknowledging,
                  onPressed: _handleAcknowledge,
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSectionCard({
    required String title,
    required IconData icon,
    required String content,
  }) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.cardBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 22, color: AppColors.primary),
              const SizedBox(width: 8),
              Text(
                title,
                style: AppText.subhead.copyWith(color: AppColors.primaryDark),
              ),
            ],
          ),
          const Divider(height: 20),
          AccessibleText(
            content,
            style: AppText.body.copyWith(height: 1.5),
          ),
        ],
      ),
    );
  }
}
