/// AddMedicationScreen — Add Medication with Drug Search & Inline Safety Check.
///
/// Features:
/// - Instant Drug Catalog search (generic & brand names)
/// - Integrated OCR Scanner shortcut
/// - Dosage & frequency scheduling
/// - Inline Drug-Drug Interaction Safety Verification
/// - Low tap count (<= 3 taps flow)
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../state/medication_provider.dart';
import '../theme/colors.dart';
import '../theme/typography.dart';
import '../widgets/big_button.dart';
import '../widgets/disclaimer_banner.dart';

class AddMedicationScreen extends ConsumerStatefulWidget {
  final Map<String, dynamic>? prefilledDrug;

  const AddMedicationScreen({super.key, this.prefilledDrug});

  @override
  ConsumerState<AddMedicationScreen> createState() => _AddMedicationScreenState();
}

class _AddMedicationScreenState extends ConsumerState<AddMedicationScreen> {
  final _formKey = GlobalKey<FormState>();
  final _searchController = TextEditingController();
  final _dosageController = TextEditingController(text: '10');
  final _notesController = TextEditingController();

  Map<String, dynamic>? _selectedDrug;
  String _selectedUnit = 'mg';
  final List<String> _units = ['mg', 'mcg', 'g', 'ml', 'units', 'tablets', 'capsules', 'puffs'];

  TimeOfDay _scheduledTime = const TimeOfDay(hour: 8, minute: 0);

  @override
  void initState() {
    super.initState();
    if (widget.prefilledDrug != null) {
      _selectedDrug = widget.prefilledDrug;
      _searchController.text = widget.prefilledDrug!['generic_name'] ?? '';
    }
  }

  @override
  void dispose() {
    _searchController.dispose();
    _dosageController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _pickTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _scheduledTime,
    );
    if (picked != null) {
      setState(() => _scheduledTime = picked);
    }
  }

  Future<void> _handleSave() async {
    if (_selectedDrug == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select a medication from the catalog')),
      );
      return;
    }

    if (!_formKey.currentState!.validate()) return;

    final drugId = _selectedDrug!['drug_id'] as String;
    final dosageAmount = double.tryParse(_dosageController.text) ?? 10.0;
    final timeStr =
        '${_scheduledTime.hour.toString().padLeft(2, '0')}:${_scheduledTime.minute.toString().padLeft(2, '0')}';

    final res = await ref.read(medicationProvider.notifier).addMedication(
          drugId: drugId,
          dosageAmount: dosageAmount,
          dosageUnit: _selectedUnit,
          schedules: [
            {'time_of_day': timeStr, 'days_of_week': []},
          ],
          notes: _notesController.text.trim().isNotEmpty ? _notesController.text.trim() : null,
        );

    if (res != null && mounted) {
      final interactionCheck = res['interaction_check'] as Map<String, dynamic>?;
      final interactions = interactionCheck?['interactions'] as List? ?? [];

      if (interactions.isNotEmpty) {
        // Show dialog or alert warning
        await showDialog(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Row(
              children: [
                Icon(Icons.warning_rounded, color: AppColors.severityMajor),
                SizedBox(width: 8),
                Text('Safety Warning'),
              ],
            ),
            content: Text(
              '${interactions.length} interaction(s) detected with your active medications. '
              'Please review your alerts list.',
              style: AppText.body,
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(),
                child: const Text('OK'),
              ),
            ],
          ),
        );
      }

      if (mounted) {
        context.pop();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final medState = ref.watch(medicationProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Add Medication', style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const DisclaimerBanner(isCompact: true),
                const SizedBox(height: 16),

                // Drug Search Header
                Text('1. SELECT MEDICATION', style: AppText.caption.copyWith(fontWeight: FontWeight.bold, color: AppColors.primaryDark)),
                const SizedBox(height: 8),

                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _searchController,
                        decoration: InputDecoration(
                          hintText: 'Search generic or brand name...',
                          prefixIcon: const Icon(Icons.search),
                          suffixIcon: _searchController.text.isNotEmpty
                              ? IconButton(
                                  icon: const Icon(Icons.clear),
                                  onPressed: () {
                                    _searchController.clear();
                                    ref.read(medicationProvider.notifier).searchCatalog('');
                                    setState(() => _selectedDrug = null);
                                  },
                                )
                              : null,
                          border: const OutlineInputBorder(),
                          filled: true,
                          fillColor: Colors.white,
                        ),
                        onChanged: (v) => ref.read(medicationProvider.notifier).searchCatalog(v),
                      ),
                    ),
                    const SizedBox(width: 8),
                    IconButton.filled(
                      onPressed: () => context.push('/scan'),
                      icon: const Icon(Icons.camera_alt),
                      tooltip: 'Scan Medication Label',
                      style: IconButton.styleFrom(
                        backgroundColor: AppColors.primary,
                        padding: const EdgeInsets.all(14),
                      ),
                    ),
                  ],
                ),

                // Search Results Dropdown List
                if (medState.drugSearchResults.isNotEmpty && _selectedDrug == null)
                  Container(
                    margin: const EdgeInsets.only(top: 6),
                    constraints: const BoxConstraints(maxHeight: 220),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppColors.cardBorder),
                      boxShadow: const [BoxShadow(color: Colors.black12, blurRadius: 4)],
                    ),
                    child: ListView.separated(
                      shrinkWrap: true,
                      itemCount: medState.drugSearchResults.length,
                      separatorBuilder: (_, __) => const Divider(height: 1),
                      itemBuilder: (ctx, idx) {
                        final item = medState.drugSearchResults[idx];
                        final generic = item['generic_name'] as String;
                        final matched = item['matched_name'] as String? ?? generic;
                        final drugClass = item['drug_class'] as String? ?? '';

                        return ListTile(
                          title: Text(
                            generic.toUpperCase(),
                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                          ),
                          subtitle: Text(
                            matched != generic ? 'Matched: $matched • $drugClass' : drugClass,
                            style: const TextStyle(fontSize: 13),
                          ),
                          onTap: () {
                            setState(() {
                              _selectedDrug = item;
                              _searchController.text = generic.toUpperCase();
                            });
                            ref.read(medicationProvider.notifier).searchCatalog('');
                          },
                        );
                      },
                    ),
                  ),

                // Selected Drug Confirmation Card
                if (_selectedDrug != null) ...[
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: AppColors.primaryLight,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: AppColors.primary, width: 1.5),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.check_circle, color: AppColors.primary, size: 28),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                (_selectedDrug!['generic_name'] as String).toUpperCase(),
                                style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold, color: AppColors.primaryDark),
                              ),
                              if (_selectedDrug!['drug_class'] != null)
                                Text(_selectedDrug!['drug_class'], style: const TextStyle(fontSize: 13, color: AppColors.textSecondary)),
                            ],
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.edit, color: AppColors.primary),
                          onPressed: () => setState(() => _selectedDrug = null),
                        ),
                      ],
                    ),
                  ),
                ],

                const SizedBox(height: 24),

                // Dosage Section
                Text('2. DOSAGE & UNIT', style: AppText.caption.copyWith(fontWeight: FontWeight.bold, color: AppColors.primaryDark)),
                const SizedBox(height: 8),

                Row(
                  children: [
                    Expanded(
                      flex: 2,
                      child: TextFormField(
                        controller: _dosageController,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: const InputDecoration(
                          labelText: 'Dosage Amount',
                          border: OutlineInputBorder(),
                          filled: true,
                          fillColor: Colors.white,
                        ),
                        style: const TextStyle(fontSize: 16),
                        validator: (v) {
                          if (v == null || v.trim().isEmpty) return 'Enter amount';
                          final num = double.tryParse(v);
                          if (num == null || num <= 0) return 'Must be > 0';
                          return null;
                        },
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      flex: 2,
                      child: DropdownButtonFormField<String>(
                        value: _selectedUnit,
                        decoration: const InputDecoration(
                          labelText: 'Unit',
                          border: OutlineInputBorder(),
                          filled: true,
                          fillColor: Colors.white,
                        ),
                        items: _units
                            .map((u) => DropdownMenuItem(value: u, child: Text(u)))
                            .toList(),
                        onChanged: (v) {
                          if (v != null) setState(() => _selectedUnit = v);
                        },
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 24),

                // Schedule Section
                Text('3. TIME OF DAY', style: AppText.caption.copyWith(fontWeight: FontWeight.bold, color: AppColors.primaryDark)),
                const SizedBox(height: 8),

                Card(
                  elevation: 1,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  child: ListTile(
                    leading: const Icon(Icons.access_time_filled, color: AppColors.primary, size: 28),
                    title: Text(
                      'Daily at ${_scheduledTime.format(context)}',
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                    subtitle: const Text('Tap to change time'),
                    trailing: const Icon(Icons.edit_calendar),
                    onTap: _pickTime,
                  ),
                ),

                const SizedBox(height: 24),

                // Optional Notes
                TextFormField(
                  controller: _notesController,
                  maxLines: 2,
                  decoration: const InputDecoration(
                    labelText: 'Notes (e.g. take with food)',
                    border: OutlineInputBorder(),
                    filled: true,
                    fillColor: Colors.white,
                  ),
                ),

                const SizedBox(height: 32),

                BigButton(
                  text: 'Save Medication & Check Safety',
                  isLoading: medState.isLoading,
                  onPressed: _handleSave,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
