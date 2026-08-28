/// OnboardingScreen — User Registration & Login with Caregiver Mode.
///
/// Features:
/// - Tabbed Login & Register forms
/// - Accessible form inputs with validation
/// - Mandatory safety disclaimer
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../state/auth_provider.dart';
import '../theme/colors.dart';
import '../theme/typography.dart';
import '../widgets/big_button.dart';
import '../widgets/disclaimer_banner.dart';

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  // Login form controllers
  final _loginFormKey = GlobalKey<FormState>();
  final _loginIdentifierController = TextEditingController();
  final _loginPasswordController = TextEditingController();

  // Register form controllers
  final _registerFormKey = GlobalKey<FormState>();
  final _regFullNameController = TextEditingController();
  final _regIdentifierController = TextEditingController();
  final _regDobController = TextEditingController();
  final _regPasswordController = TextEditingController();
  DateTime? _selectedDob;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    _loginIdentifierController.dispose();
    _loginPasswordController.dispose();
    _regFullNameController.dispose();
    _regIdentifierController.dispose();
    _regDobController.dispose();
    _regPasswordController.dispose();
    super.dispose();
  }

  Future<void> _handleLogin() async {
    if (!_loginFormKey.currentState!.validate()) return;

    final success = await ref.read(authProvider.notifier).login(
          emailOrPhone: _loginIdentifierController.text.trim(),
          password: _loginPasswordController.text,
        );

    if (success && mounted) {
      context.go('/medications');
    }
  }

  Future<void> _handleRegister() async {
    if (!_registerFormKey.currentState!.validate()) return;
    if (_selectedDob == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select your date of birth')),
      );
      return;
    }

    final identifier = _regIdentifierController.text.trim();
    final isEmail = identifier.contains('@');

    final success = await ref.read(authProvider.notifier).register(
          fullName: _regFullNameController.text.trim(),
          dateOfBirth: _regDobController.text.trim(),
          email: isEmail ? identifier : null,
          phoneNumber: isEmail ? null : identifier,
          password: _regPasswordController.text,
        );

    if (success && mounted) {
      context.go('/medications');
    }
  }

  Future<void> _pickDateOfBirth() async {
    final now = DateTime.now();
    final initial = DateTime(1970, 1, 1);
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDob ?? initial,
      firstDate: DateTime(1900),
      lastDate: now,
      helpText: 'Select Date of Birth',
    );
    if (picked != null) {
      setState(() {
        _selectedDob = picked;
        _regDobController.text =
            '${picked.year}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('CascadeX — Safety Portal', style: TextStyle(fontWeight: FontWeight.bold)),
        centerTitle: true,
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Header Brand Banner
              Container(
                padding: const EdgeInsets.symmetric(vertical: 16),
                child: Column(
                  children: [
                    const Icon(Icons.shield_outlined, size: 56, color: AppColors.primary),
                    const SizedBox(height: 8),
                    Text('Drug Safety & Interaction Monitor', style: AppText.headline.copyWith(color: AppColors.primaryDark)),
                    const SizedBox(height: 4),
                    const Text('Clinical verification for polypharmacy regimens', style: AppText.caption),
                  ],
                ),
              ),

              const DisclaimerBanner(isCompact: true),
              const SizedBox(height: 16),

              if (authState.errorMessage != null)
                Container(
                  margin: const EdgeInsets.only(bottom: 16),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.errorBg,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.error),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.error_outline_rounded, color: AppColors.error),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          authState.errorMessage!,
                          style: const TextStyle(color: AppColors.error, fontSize: 14, fontWeight: FontWeight.w500),
                        ),
                      ),
                    ],
                  ),
                ),

              // Tab Bar (Login vs Register)
              Container(
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  boxShadow: const [
                    BoxShadow(color: Colors.black12, blurRadius: 4, offset: Offset(0, 2)),
                  ],
                ),
                child: Column(
                  children: [
                    TabBar(
                      controller: _tabController,
                      labelColor: AppColors.primary,
                      unselectedLabelColor: AppColors.textSecondary,
                      labelStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                      indicatorColor: AppColors.primary,
                      indicatorWeight: 3,
                      tabs: const [
                        Tab(text: 'Sign In'),
                        Tab(text: 'Create Account'),
                      ],
                    ),
                    Padding(
                      padding: const EdgeInsets.all(20),
                      child: SizedBox(
                        height: 380,
                        child: TabBarView(
                          controller: _tabController,
                          children: [
                            _buildLoginForm(authState),
                            _buildRegisterForm(authState),
                          ],
                        ),
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

  Widget _buildLoginForm(AuthState authState) {
    return Form(
      key: _loginFormKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextFormField(
            controller: _loginIdentifierController,
            decoration: const InputDecoration(
              labelText: 'Email or Phone Number',
              prefixIcon: Icon(Icons.person_outline),
              border: OutlineInputBorder(),
            ),
            style: const TextStyle(fontSize: 16),
            validator: (v) => (v == null || v.trim().isEmpty) ? 'Please enter email or phone' : null,
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _loginPasswordController,
            obscureText: true,
            decoration: const InputDecoration(
              labelText: 'Password',
              prefixIcon: Icon(Icons.lock_outline),
              border: OutlineInputBorder(),
            ),
            style: const TextStyle(fontSize: 16),
            validator: (v) => (v == null || v.isEmpty) ? 'Please enter password' : null,
          ),
          const SizedBox(height: 24),
          BigButton(
            text: 'Sign In',
            isLoading: authState.isLoading,
            onPressed: _handleLogin,
          ),
          const SizedBox(height: 12),
          TextButton(
            onPressed: () {
              // demo quick-fill
              _loginIdentifierController.text = 'patient@cascadex.test';
              _loginPasswordController.text = 'Password123!';
            },
            child: const Text('Fill Demo Credentials', style: TextStyle(fontSize: 14)),
          ),
        ],
      ),
    );
  }

  Widget _buildRegisterForm(AuthState authState) {
    return Form(
      key: _registerFormKey,
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextFormField(
              controller: _regFullNameController,
              decoration: const InputDecoration(
                labelText: 'Full Name',
                prefixIcon: Icon(Icons.badge_outlined),
                border: OutlineInputBorder(),
              ),
              style: const TextStyle(fontSize: 16),
              validator: (v) => (v == null || v.trim().isEmpty) ? 'Full name is required' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _regIdentifierController,
              decoration: const InputDecoration(
                labelText: 'Email or Phone Number',
                prefixIcon: Icon(Icons.contact_mail_outlined),
                border: OutlineInputBorder(),
              ),
              style: const TextStyle(fontSize: 16),
              validator: (v) => (v == null || v.trim().isEmpty) ? 'Email or phone required' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _regDobController,
              readOnly: true,
              onTap: _pickDateOfBirth,
              decoration: const InputDecoration(
                labelText: 'Date of Birth (YYYY-MM-DD)',
                prefixIcon: Icon(Icons.calendar_today_outlined),
                border: OutlineInputBorder(),
              ),
              style: const TextStyle(fontSize: 16),
              validator: (v) => (v == null || v.isEmpty) ? 'Select date of birth' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _regPasswordController,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'Password (min 8 chars)',
                prefixIcon: Icon(Icons.lock_outline),
                border: OutlineInputBorder(),
              ),
              style: const TextStyle(fontSize: 16),
              validator: (v) => (v == null || v.length < 8) ? 'Minimum 8 characters required' : null,
            ),
            const SizedBox(height: 20),
            BigButton(
              text: 'Create Account',
              isLoading: authState.isLoading,
              onPressed: _handleRegister,
            ),
          ],
        ),
      ),
    );
  }
}
