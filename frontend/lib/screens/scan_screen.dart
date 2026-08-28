/// CascadeX Scan Screen — Phase 05.
///
/// Integrates `image_picker` for camera capture + `OcrService` for on-device
/// ML Kit OCR. Sends only the extracted *text* to the backend; raw images
/// are never transmitted (per PROJECT_OVERVIEW.md §8 privacy rule).
///
/// Flow:
///   1. User taps "Scan Medication" button.
///   2. Camera opens (via `image_picker`).
///   3. On capture: ML Kit extracts text on-device.
///   4. Text POSTed to `/api/v1/scans`.
///   5. User navigated to `ScanConfirmationScreen` with candidates.
library;

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../services/ocr_service.dart';
import 'scan_confirmation_screen.dart';

class ScanScreen extends StatefulWidget {
  /// JWT access token forwarded to [OcrService].
  final String accessToken;

  const ScanScreen({super.key, required this.accessToken});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  bool _isProcessing = false;
  String? _errorMessage;

  final ImagePicker _picker = ImagePicker();

  // ---------------------------------------------------------------------------
  // Camera capture + OCR
  // ---------------------------------------------------------------------------

  Future<void> _scanWithCamera() async {
    setState(() {
      _isProcessing = false;
      _errorMessage = null;
    });

    XFile? image;
    try {
      image = await _picker.pickImage(
        source: ImageSource.camera,
        maxWidth: 1920,
        maxHeight: 1080,
        imageQuality: 85,
      );
    } catch (e) {
      setState(() => _errorMessage = 'Camera unavailable: $e');
      return;
    }

    if (image == null) {
      // User cancelled — do nothing.
      return;
    }

    setState(() => _isProcessing = true);

    try {
      final ocrService = OcrService(accessToken: widget.accessToken);
      final result = await ocrService.extractAndMatch(image.path);

      if (!mounted) return;

      if (result.ocrText.trim().isEmpty || result.status == 'unmatched' && result.scanId.isEmpty) {
        // No text extracted — show inline error and let user retry.
        setState(() {
          _isProcessing = false;
          _errorMessage = result.message.isNotEmpty
              ? result.message
              : 'No text detected. Please try again with better lighting.';
        });
        return;
      }

      // Navigate to confirmation screen — user must explicitly confirm before
      // any medication is added (Phase 05 invariant: no silent auto-add).
      setState(() => _isProcessing = false);
      if (!mounted) return;
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => ScanConfirmationScreen(
            scanResult: result,
            accessToken: widget.accessToken,
          ),
        ),
      );
    } on OcrServiceException catch (e) {
      if (!mounted) return;
      setState(() {
        _isProcessing = false;
        _errorMessage = 'Could not contact the server. Please try again.';
      });
      debugPrint('OcrServiceException: $e');
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isProcessing = false;
        _errorMessage = 'Something went wrong. Please try again.';
      });
      debugPrint('ScanScreen error: $e');
    }
  }

  /// Allow manual text entry as a fallback for users who can't use the camera.
  Future<void> _scanManualEntry(String text) async {
    if (text.trim().isEmpty) return;

    setState(() {
      _isProcessing = true;
      _errorMessage = null;
    });

    try {
      final ocrService = OcrService(accessToken: widget.accessToken);
      final result = await ocrService.submitText(text.trim());

      if (!mounted) return;
      setState(() => _isProcessing = false);

      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => ScanConfirmationScreen(
            scanResult: result,
            accessToken: widget.accessToken,
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isProcessing = false;
        _errorMessage = 'Something went wrong. Please try again.';
      });
    }
  }

  // ---------------------------------------------------------------------------
  // Build
  // ---------------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan Medication'),
        backgroundColor: colorScheme.primaryContainer,
        foregroundColor: colorScheme.onPrimaryContainer,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // ── Instruction card ────────────────────────────────────────────
            Card(
              elevation: 2,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  children: [
                    Icon(
                      Icons.document_scanner_outlined,
                      size: 72,
                      color: colorScheme.primary,
                      semanticLabel: 'Document scanner icon',
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'Scan a medicine label',
                      style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Point your camera at the medication box or prescription label. '
                      'Text is processed privately on your device — no image leaves your phone.',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: colorScheme.onSurfaceVariant,
                          ),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 24),

            // ── Error message ───────────────────────────────────────────────
            if (_errorMessage != null)
              Semantics(
                liveRegion: true,
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: colorScheme.errorContainer,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.error_outline, color: colorScheme.error),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          _errorMessage!,
                          style: TextStyle(color: colorScheme.onErrorContainer),
                        ),
                      ),
                    ],
                  ),
                ),
              ),

            if (_errorMessage != null) const SizedBox(height: 16),

            // ── Main scan button ────────────────────────────────────────────
            if (_isProcessing)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 32),
                child: Column(
                  children: [
                    CircularProgressIndicator(),
                    SizedBox(height: 16),
                    Text('Processing scan…'),
                  ],
                ),
              )
            else ...[
              Semantics(
                button: true,
                label: 'Open camera to scan medication label',
                child: ElevatedButton.icon(
                  onPressed: _scanWithCamera,
                  icon: const Icon(Icons.camera_alt, size: 28),
                  label: const Text(
                    'Open Camera',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
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

              const Row(
                children: [
                  Expanded(child: Divider()),
                  Padding(
                    padding: EdgeInsets.symmetric(horizontal: 12),
                    child: Text('or type the drug name'),
                  ),
                  Expanded(child: Divider()),
                ],
              ),

              const SizedBox(height: 12),

              _ManualEntryField(onSubmit: _scanManualEntry),
            ],

            const SizedBox(height: 32),

            // ── Disclaimer ──────────────────────────────────────────────────
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
                    Icon(Icons.info_outline, size: 20, color: colorScheme.tertiary),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        '⚠️ Scan results require your confirmation before any medication is added. '
                        'This is not a substitute for advice from a pharmacist or doctor.',
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
// Manual entry fallback widget
// ---------------------------------------------------------------------------

class _ManualEntryField extends StatefulWidget {
  final Future<void> Function(String text) onSubmit;

  const _ManualEntryField({required this.onSubmit});

  @override
  State<_ManualEntryField> createState() => _ManualEntryFieldState();
}

class _ManualEntryFieldState extends State<_ManualEntryField> {
  final _controller = TextEditingController();
  bool _submitting = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Semantics(
            label: 'Drug name text field',
            textField: true,
            child: TextField(
              controller: _controller,
              decoration: const InputDecoration(
                hintText: 'e.g. warfarin, Coumadin',
                border: OutlineInputBorder(),
                contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              ),
              textInputAction: TextInputAction.search,
              onSubmitted: (_) async {
                setState(() => _submitting = true);
                await widget.onSubmit(_controller.text);
                if (mounted) setState(() => _submitting = false);
              },
            ),
          ),
        ),
        const SizedBox(width: 10),
        Semantics(
          button: true,
          label: 'Search for drug name',
          child: IconButton.filled(
            onPressed: _submitting
                ? null
                : () async {
                    setState(() => _submitting = true);
                    await widget.onSubmit(_controller.text);
                    if (mounted) setState(() => _submitting = false);
                  },
            icon: const Icon(Icons.search),
            iconSize: 28,
            style: IconButton.styleFrom(
              minimumSize: const Size(56, 56),
            ),
          ),
        ),
      ],
    );
  }
}
