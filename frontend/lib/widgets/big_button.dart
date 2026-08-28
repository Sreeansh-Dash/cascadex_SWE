/// BigButton — Accessible high-contrast button with minimum 48×48dp tap target.
///
/// Ensures compliance with WCAG 2.1 AAA target size requirements for touch screens.
library;

import 'package:flutter/material.dart';
import '../theme/colors.dart';
import '../theme/typography.dart';

class BigButton extends StatelessWidget {
  final String text;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool isLoading;
  final Color? backgroundColor;
  final Color? textColor;
  final bool isSecondary;
  final double minHeight;

  const BigButton({
    super.key,
    required this.text,
    required this.onPressed,
    this.icon,
    this.isLoading = false,
    this.backgroundColor,
    this.textColor,
    this.isSecondary = false,
    this.minHeight = 52.0,
  });

  @override
  Widget build(BuildContext context) {
    final bg = isSecondary
        ? (backgroundColor ?? Colors.transparent)
        : (backgroundColor ?? AppColors.primary);

    final fg = isSecondary
        ? (textColor ?? AppColors.primary)
        : (textColor ?? Colors.white);

    return Semantics(
      button: true,
      enabled: onPressed != null && !isLoading,
      label: text,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          minWidth: double.infinity,
          minHeight: minHeight,
        ),
        child: isSecondary
            ? OutlinedButton(
                onPressed: isLoading ? null : onPressed,
                style: OutlinedButton.styleFrom(
                  side: BorderSide(color: fg, width: 1.5),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
                ),
                child: _buildChild(fg),
              )
            : ElevatedButton(
                onPressed: isLoading ? null : onPressed,
                style: ElevatedButton.styleFrom(
                  backgroundColor: bg,
                  foregroundColor: fg,
                  elevation: 2,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
                ),
                child: _buildChild(fg),
              ),
      ),
    );
  }

  Widget _buildChild(Color fg) {
    if (isLoading) {
      return SizedBox(
        height: 24,
        width: 24,
        child: CircularProgressIndicator(
          strokeWidth: 2.5,
          valueColor: AlwaysStoppedAnimation<Color>(fg),
        ),
      );
    }

    if (icon != null) {
      return Row(
        mainAxisAlignment: MainAxisAlignment.center,
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 22, color: fg),
          const SizedBox(width: 10),
          Text(
            text,
            style: AppText.button.copyWith(color: fg),
          ),
        ],
      );
    }

    return Text(
      text,
      style: AppText.button.copyWith(color: fg),
      textAlign: TextAlign.center,
    );
  }
}
