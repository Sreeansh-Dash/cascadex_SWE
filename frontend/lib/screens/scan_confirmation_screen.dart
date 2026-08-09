/// CascadeX Scan Confirmation Screen — Phase 05.
///
/// Shows the proposed drug match from `POST /scans` and requires an explicit
/// "Confirm & Add" tap before calling `POST /medications`.
///
/// Safety invariant (non-negotiable, per 05-OCR-SCAN-FLOW.md):
///   - This screen NEVER calls POST /medications without a deliberate user tap.
///   - No auto-advance timers.
///   - Navigating back without confirming = nothing is added (tested in
///     `scan_confirmation_test.dart`).
library;

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

import '../services/ocr_service.dart';

/// Called after user taps "Confirm & Add".
/// Receives the confirmed drug_id for callers who need it.
typedef OnMedicationAdded = void Function(String drugId);

class ScanConfirmationScreen extends StatefulWidget {
  final OcrScanResult scanResult;
  final String accessToken;

  /// Optional callback invoked when the user successfully adds a medication.
  final OnMedicationAdded? onMedicationAdded;

  const ScanConfirmationScreen({
    super.key,
    required this.scanResult,
    required this.accessToken,
    this.onMedicationAdded,
  });

  @override
  State<ScanConfirmationScreen> createState() => _ScanConfirmationScreenState();
}

class _ScanConfirmationScreenState extends State<ScanConfirmationScreen> {
  // Currently selected drug (starts as the primary match, if any).
  Map<String, dynamic>? _selectedDrug;
  bool _isAdding = false;
  String? _errorMessage;
  bool _added = false;

  String get _baseUrl => 'http://10.0.2.2:8000/api/v1';

  @override
  void initState() {
    super.initState();
    _selectedDrug = widget.scanResult.primaryMatch;
  }

  // ---------------------------------------------------------------------------
  // POST /medications  (Phase 04 endpoint — reused here, not duplicated)
  // ---------------------------------------------------------------------------

  Future<void> _confirmAndAdd() async {
    if (_selectedDrug == null) return;

    setState(() {
      _isAdding = true;
      _errorMessage = null;
    });

    try {
      final uri = Uri.parse('$_baseUrl/medications');
      final response = await http.post(
        uri,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ${widget.accessToken}',
        },
        body: jsonEncode({
          'drug_id': _selectedDrug!['drug_id'],
          'input_method': 'scan',
          'notes': 'Added via scan (scan_id: ${widget.scanResult.scanId})',
        }),
      );

      if (!mounted) return;

      if (response.statusCode == 201) {
        setState(() {
          _isAdding = false;
          _added = true;
        });
        widget.onMedicationAdded?.call(_selectedDrug!['drug_id'] as String);
        _showSuccessAndPop();
      } else {
        final body = jsonDecode(response.body);
        setState(() {
          _isAdding = false;
          _errorMessage = body['message'] as String? ?? 'Failed to add medication.';
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isAdding = false;
        _errorMessage = 'Network error. Please check your connection and try again.';
      });
    }
  }

  void _showSuccessAndPop() {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          '${_selectedDrug!['generic_name']} added to your medications.',
        ),
        backgroundColor: Colors.green.shade700,
        duration: const Duration(seconds: 3),
      ),
    );
    // Pop back to the scan screen (or medication list if pushed from there).
    Navigator.of(context).pop(true); // true = medication was added
  }

  // ---------------------------------------------------------------------------
  // Build
  // ---------------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final hasMatch = widget.scanResult.primaryMatch != null;
    final candidates = widget.scanResult.candidates;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Confirm Medication'),
        backgroundColor: colorScheme.primaryContainer,
        foregroundColor: colorScheme.onPrimaryContainer,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // ── Scanned text display ─────────────────────────────────────
            Semantics(
              label: 'Scanned text: ${widget.scanResult.ocrText}',
              child: Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: colorScheme.surfaceVariant,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.text_snippet_outlined,
                            size: 18, color: colorScheme.primary),
                        const SizedBox(width: 8),
                        Text(
                          'Scanned text',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: colorScheme.primary,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      widget.scanResult.ocrText,
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 20),

            // ── Match result header ──────────────────────────────────────
            if (!hasMatch) ...[
              _NoMatchBanner(message: widget.scanResult.message),
              const SizedBox(height: 16),
            ] else ...[
              _MatchHeader(status: widget.scanResult.status),
              const SizedBox(height: 16),
            ],

            // ── Candidate selection ──────────────────────────────────────
            if (candidates.isEmpty && !hasMatch)
              Semantics(
                label: 'No drug candidates found',
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text(
                    'No matching drug found. Please search the catalog manually '
                    'via the "Add Medication" screen.',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: colorScheme.onSurfaceVariant,
                        ),
                    textAlign: TextAlign.center,
                  ),
                ),
              )
            else ...[
              Text(
                'Select the correct drug:',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
              ),
              const SizedBox(height: 10),
              ...candidates.map((drug) => _CandidateTile(
                    drug: drug,
                    isSelected: _selectedDrug?['drug_id'] == drug['drug_id'],
                    onTap: () => setState(() => _selectedDrug = drug),
                  )),
            ],

            const SizedBox(height: 20),

            // ── Error message ────────────────────────────────────────────
            if (_errorMessage != null)
              Semantics(
                liveRegion: true,
                child: Container(
                  padding: const EdgeInsets.all(14),
                  margin: const EdgeInsets.only(bottom: 14),
                  decoration: BoxDecoration(
                    color: colorScheme.errorContainer,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    _errorMessage!,
                    style: TextStyle(color: colorScheme.onErrorContainer),
                  ),
                ),
              ),

            // ── Action buttons ───────────────────────────────────────────
            if (!_added) ...[
              Semantics(
                button: true,
                label: _selectedDrug == null
                    ? 'Confirm and add medication — disabled, no drug selected'
                    : 'Confirm and add ${_selectedDrug!['generic_name']} to medications',
                child: ElevatedButton.icon(
                  onPressed: (_isAdding || _selectedDrug == null) ? null : _confirmAndAdd,
                  icon: _isAdding
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.check_circle_outline),
                  label: Text(
                    _isAdding ? 'Adding…' : 'Confirm & Add',
                    style: const TextStyle(
                        fontSize: 17, fontWeight: FontWeight.bold),
                  ),
                  style: ElevatedButton.styleFrom(
                    minimumSize: const Size(double.infinity, 56),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                    backgroundColor: colorScheme.primary,
                    foregroundColor: colorScheme.onPrimary,
                  ),
                ),
              ),

              const SizedBox(height: 12),

              Semantics(
                button: true,
                label: 'Cancel and go back without adding any medication',
                child: OutlinedButton.icon(
                  onPressed: _isAdding ? null : () => Navigator.of(context).pop(false),
                  icon: const Icon(Icons.close),
                  label: const Text(
                    'Cancel — don\'t add',
                    style: TextStyle(fontSize: 16),
                  ),
                  style: OutlinedButton.styleFrom(
                    minimumSize: const Size(double.infinity, 52),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                  ),
                ),
              ),
            ],

            const SizedBox(height: 24),

            // ── Persistent disclaimer (SRS §7) ───────────────────────────
            Semantics(
              label: 'Safety disclaimer',
              child: Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: colorScheme.tertiaryContainer,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.health_and_safety_outlined,
                        size: 20, color: colorScheme.tertiary),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        '⚠️ This is not a substitute for advice from a pharmacist or doctor. '
                        'Always verify the drug name before confirming.',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: colorScheme.onTertiaryContainer,
                            ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Sub-widgets
// ---------------------------------------------------------------------------

class _MatchHeader extends StatelessWidget {
  final String status;
  const _MatchHeader({required this.status});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final isMatched = status == 'matched';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: isMatched
            ? Colors.green.shade50
            : colorScheme.secondaryContainer,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: isMatched ? Colors.green.shade200 : colorScheme.secondary,
          width: 1.5,
        ),
      ),
      child: Row(
        children: [
          Icon(
            isMatched ? Icons.check_circle : Icons.help_outline,
            color: isMatched ? Colors.green.shade700 : colorScheme.secondary,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              isMatched
                  ? 'Match found — please review and confirm.'
                  : 'Partial match — select the correct drug below.',
              style: TextStyle(
                color: isMatched
                    ? Colors.green.shade900
                    : colorScheme.onSecondaryContainer,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _NoMatchBanner extends StatelessWidget {
  final String message;
  const _NoMatchBanner({required this.message});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Icon(Icons.search_off, color: colorScheme.error),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message.isNotEmpty ? message : 'No confident match found.',
              style: TextStyle(color: colorScheme.onErrorContainer),
            ),
          ),
        ],
      ),
    );
  }
}

class _CandidateTile extends StatelessWidget {
  final Map<String, dynamic> drug;
  final bool isSelected;
  final VoidCallback onTap;

  const _CandidateTile({
    required this.drug,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final genericName = drug['generic_name'] as String? ?? '';
    final drugClass = drug['drug_class'] as String? ?? '';

    return Semantics(
      button: true,
      selected: isSelected,
      label: isSelected
          ? '$genericName selected'
          : 'Select $genericName, drug class $drugClass',
      child: GestureDetector(
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: isSelected
                ? colorScheme.primaryContainer
                : colorScheme.surfaceVariant,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isSelected ? colorScheme.primary : Colors.transparent,
              width: 2,
            ),
          ),
          child: Row(
            children: [
              Icon(
                isSelected ? Icons.radio_button_checked : Icons.radio_button_unchecked,
                color: isSelected ? colorScheme.primary : colorScheme.onSurfaceVariant,
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      genericName,
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: isSelected
                            ? colorScheme.onPrimaryContainer
                            : colorScheme.onSurface,
                      ),
                    ),
                    if (drugClass.isNotEmpty)
                      Text(
                        drugClass,
                        style: TextStyle(
                          fontSize: 13,
                          color: isSelected
                              ? colorScheme.onPrimaryContainer.withOpacity(0.8)
                              : colorScheme.onSurfaceVariant,
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
