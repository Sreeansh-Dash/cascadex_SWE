/// HistoryScreen — Unified Medication & Safety Timeline with PDF Clinical Export.
///
/// Features:
/// - Combined timeline feed of dose intake logs and drug interaction alerts
/// - Visual discrimination of events with accessible icons & colors
/// - Direct PDF Clinical Export button
library;

import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:printing/printing.dart';

import '../state/history_provider.dart';
import '../theme/colors.dart';
import '../theme/typography.dart';
import '../widgets/disclaimer_banner.dart';

class HistoryScreen extends ConsumerStatefulWidget {
  const HistoryScreen({super.key});

  @override
  ConsumerState<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends ConsumerState<HistoryScreen> {
  String _filter = 'all'; // 'all' | 'doses' | 'alerts'

  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(historyProvider.notifier).loadInitialFeed());
  }

  Future<void> _handlePdfExport() async {
    final pdfBytes = await ref.read(historyProvider.notifier).exportPdf();
    if (pdfBytes != null && mounted) {
      await Printing.layoutPdf(
        onLayout: (_) async => Uint8List.fromList(pdfBytes),
        name: 'cascadex_medication_summary.pdf',
      );
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to export PDF summary')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final historyState = ref.watch(historyProvider);

    final filteredEvents = historyState.events.where((e) {
      if (_filter == 'doses') return e['event_type'] == 'dose';
      if (_filter == 'alerts') return e['event_type'] == 'alert';
      return true;
    }).toList();

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Medication History', style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: historyState.isExportingPdf
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : const Icon(Icons.picture_as_pdf_outlined),
            tooltip: 'Export Clinical Summary PDF',
            onPressed: historyState.isExportingPdf ? null : _handlePdfExport,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Filter Chips Bar
            Container(
              color: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Row(
                children: [
                  _buildFilterChip('All Events', 'all'),
                  const SizedBox(width: 8),
                  _buildFilterChip('Doses', 'doses'),
                  const SizedBox(width: 8),
                  _buildFilterChip('Safety Alerts', 'alerts'),
                ],
              ),
            ),

            const Padding(
              padding: EdgeInsets.fromLTRB(16, 12, 16, 4),
              child: DisclaimerBanner(isCompact: true),
            ),

            Expanded(
              child: historyState.isLoading && historyState.events.isEmpty
                  ? const Center(child: CircularProgressIndicator())
                  : RefreshIndicator(
                      onRefresh: () => ref.read(historyProvider.notifier).loadInitialFeed(),
                      child: filteredEvents.isEmpty
                          ? ListView(
                              children: const [
                                SizedBox(height: 80),
                                Center(
                                  child: Text('No historical events recorded yet.', style: AppText.body),
                                ),
                              ],
                            )
                          : ListView.builder(
                              padding: const EdgeInsets.all(16),
                              itemCount: filteredEvents.length + (historyState.hasMore ? 1 : 0),
                              itemBuilder: (ctx, idx) {
                                if (idx == filteredEvents.length) {
                                  ref.read(historyProvider.notifier).loadMore();
                                  return const Center(
                                    child: Padding(
                                      padding: EdgeInsets.all(16),
                                      child: CircularProgressIndicator(),
                                    ),
                                  );
                                }

                                final event = filteredEvents[idx];
                                return _buildTimelineItem(event);
                              },
                            ),
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFilterChip(String label, String value) {
    final isSelected = _filter == value;
    return FilterChip(
      label: Text(label),
      selected: isSelected,
      onSelected: (_) => setState(() => _filter = value),
      selectedColor: AppColors.primaryLight,
      checkmarkColor: AppColors.primary,
      labelStyle: TextStyle(
        color: isSelected ? AppColors.primaryDark : AppColors.textSecondary,
        fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
      ),
    );
  }

  Widget _buildTimelineItem(Map<String, dynamic> event) {
    final isDose = event['event_type'] == 'dose';
    final timestamp = event['timestamp'] as String? ?? '';
    final formattedDate = timestamp.length > 16
        ? timestamp.substring(0, 16).replaceFirst('T', ' ')
        : timestamp;

    if (isDose) {
      final genericName = (event['generic_name'] as String? ?? 'Medication').toUpperCase();
      final status = (event['status'] as String? ?? 'taken').toLowerCase();
      final dosage = '${event['dosage_amount']} ${event['dosage_unit']}';

      IconData statusIcon;
      Color statusColor;
      String statusText;

      switch (status) {
        case 'taken':
          statusIcon = Icons.check_circle_rounded;
          statusColor = AppColors.success;
          statusText = 'TAKEN';
          break;
        case 'skipped':
          statusIcon = Icons.pause_circle_filled_rounded;
          statusColor = AppColors.warning;
          statusText = 'SKIPPED';
          break;
        default:
          statusIcon = Icons.cancel_rounded;
          statusColor = AppColors.error;
          statusText = 'MISSED';
          break;
      }

      return Card(
        margin: const EdgeInsets.only(bottom: 12),
        elevation: 1.5,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        child: ListTile(
          leading: Icon(statusIcon, color: statusColor, size: 36),
          title: Text(
            genericName,
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
          ),
          subtitle: Text('$dosage • $formattedDate\nStatus: $statusText'),
          isThreeLine: true,
        ),
      );
    } else {
      // Alert event
      final drugA = (event['drug_a_name'] as String? ?? 'Drug A').toUpperCase();
      final drugB = (event['drug_b_name'] as String? ?? 'Drug B').toUpperCase();
      final severity = event['severity'] as String? ?? 'major';
      final ack = event['acknowledged'] as bool? ?? false;

      return Card(
        margin: const EdgeInsets.only(bottom: 12),
        elevation: 2,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: AppColors.severityMajor, width: 1.5),
        ),
        color: AppColors.severityMajorBg.withOpacity(0.4),
        child: ListTile(
          leading: const Icon(Icons.warning_rounded, color: AppColors.severityMajor, size: 36),
          title: Text(
            'SAFETY ALERT: $drugA + $drugB',
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: AppColors.severityMajor),
          ),
          subtitle: Text(
            'Severity: ${severity.toUpperCase()} • $formattedDate\n'
            '${ack ? "Acknowledged ✅" : "Pending Acknowledgment ⚠️"}',
          ),
          isThreeLine: true,
          trailing: const Icon(Icons.chevron_right),
          onTap: () => context.push('/alerts/detail', extra: event),
        ),
      );
    }
  }
}
