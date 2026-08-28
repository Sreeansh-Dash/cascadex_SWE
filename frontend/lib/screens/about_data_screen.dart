/// AboutDataScreen — Clinical Data Source Attributions & Safety Invariants.
///
/// Features:
/// - DDInter 2.0 and NLM RxNorm knowledgebase version details
/// - Core architectural safety invariants explanation
/// - Medical disclaimer
library;

import 'package:flutter/material.dart';
import '../theme/colors.dart';
import '../theme/typography.dart';
import '../widgets/accessible_text.dart';
import '../widgets/disclaimer_banner.dart';

class AboutDataScreen extends StatelessWidget {
  const AboutDataScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('About Safety Data', style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            const DisclaimerBanner(),
            const SizedBox(height: 20),

            // Dataset Version Box
            Card(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.dataset_outlined, color: AppColors.primary, size: 28),
                        const SizedBox(width: 10),
                        Text(
                          'Clinical Datasets',
                          style: AppText.headline.copyWith(color: AppColors.primaryDark),
                        ),
                      ],
                    ),
                    const Divider(height: 24),
                    _buildDatasetRow('DDInter Clinical DDI Database', 'Version 2.0 (Peer-Reviewed)'),
                    const SizedBox(height: 10),
                    _buildDatasetRow('NLM RxNorm Catalog', 'Standardized Drug Formulations'),
                    const SizedBox(height: 10),
                    _buildDatasetRow('Graph Knowledgebase', 'Neo4j 5.x Property Graph Engine'),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 20),

            // Safety Invariants Card
            Card(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.security_rounded, color: AppColors.primary, size: 28),
                        const SizedBox(width: 10),
                        Text(
                          'Safety Invariants',
                          style: AppText.headline.copyWith(color: AppColors.primaryDark),
                        ),
                      ],
                    ),
                    const Divider(height: 24),
                    _buildInvariantItem(
                      '1. Unmatched ≠ Safe',
                      'If any medication cannot be resolved in the clinical catalog, an explicit warning is generated. The system never silently drops unresolvable drugs.',
                    ),
                    const SizedBox(height: 14),
                    _buildInvariantItem(
                      '2. Never Invent an Interaction',
                      'All drug interactions are verified against real, indexed graph database edges. Generative AI is only used to rewrite clinical text into plain language, never to decide if an interaction exists.',
                    ),
                    const SizedBox(height: 14),
                    _buildInvariantItem(
                      '3. On-Device Privacy First',
                      'Prescription label OCR runs 100% on-device using ML Kit. Raw camera images are never stored or transmitted across the network.',
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 20),

            // Academic Notice
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.cardBorder),
              ),
              child: Column(
                children: [
                  const Icon(Icons.school_outlined, color: AppColors.textMuted, size: 36),
                  const SizedBox(height: 8),
                  Text(
                    'CascadeX — Software Engineering Project',
                    style: AppText.subhead.copyWith(color: AppColors.textPrimary),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Developed as an advanced academic clinical safety demonstration system.',
                    style: AppText.caption,
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Widget _buildDatasetRow(String title, String subtitle) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
        Text(subtitle, style: const TextStyle(color: AppColors.textSecondary, fontSize: 14)),
      ],
    );
  }

  Widget _buildInvariantItem(String title, String description) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: AppColors.primary),
        ),
        const SizedBox(height: 4),
        AccessibleText(
          description,
          style: const TextStyle(fontSize: 14, height: 1.4, color: AppColors.textSecondary),
        ),
      ],
    );
  }
}
