// screens/RegisterScreen.js
// Mirrors register.html — centered glass-card, gradient brand,
// animated bg blobs, uppercase labels, password-strength dot
import React, { useState, useRef, useEffect } from 'react';
import {
    View, Text, TextInput, TouchableOpacity, StyleSheet,
    ActivityIndicator, ScrollView, Alert, Animated, KeyboardAvoidingView, Platform,
} from 'react-native';
import { apiPost } from '../api';

// Animated glowing blob (mirrors .bg-blob CSS animation)
function Blob({ style }) {
    const anim = useRef(new Animated.Value(0)).current;
    useEffect(() => {
        Animated.loop(
            Animated.sequence([
                Animated.timing(anim, { toValue: 1, duration: 4000, useNativeDriver: true }),
                Animated.timing(anim, { toValue: 0, duration: 4000, useNativeDriver: true }),
            ])
        ).start();
    }, []);
    const translate = anim.interpolate({ inputRange: [0, 1], outputRange: [0, 40] });
    return (
        <Animated.View
            style={[style, { transform: [{ translateY: translate }] }]}
            pointerEvents="none"
        />
    );
}

export default function RegisterScreen({ navigation }) {
    const [form, setForm] = useState({
        username: '', email: '', password: '', confirm_password: '',
    });
    const [loading, setLoading] = useState(false);
    const [errorMsg, setErrorMsg] = useState('');
    const [successMsg, setSuccessMsg] = useState('');

    const set = (k) => (v) => {
        setForm(f => ({ ...f, [k]: v }));
        setErrorMsg('');
        setSuccessMsg('');
    };

    // Password requirement dot: turns green when ≥6 chars
    const pwMet = form.password.length >= 6;

    const handleRegister = async () => {
        const { username, email, password, confirm_password } = form;
        if (!username || !email || !password || !confirm_password) {
            setErrorMsg('All fields are required'); return;
        }
        if (password !== confirm_password) {
            setErrorMsg('Authentication keys do not match'); return;
        }
        if (password.length < 6) {
            setErrorMsg('Policy: Minimum 6 cryptographic characters'); return;
        }
        setLoading(true);
        setErrorMsg('');
        setSuccessMsg('');
        try {
            const data = await apiPost('/api/register', form);
            if (data.success) {
                setSuccessMsg('Identity created. Redirecting to gateway...');
                setTimeout(() => navigation.replace('Login'), 1500);
            } else {
                setErrorMsg(data.message || 'Credential issuance failed');
            }
        } catch {
            setErrorMsg('Identity server unreachable');
        } finally {
            setLoading(false);
        }
    };

    return (
        <View style={s.bg}>
            {/* Animated background blobs */}
            <Blob style={s.blob1} />
            <Blob style={s.blob2} />

            <KeyboardAvoidingView
                style={{ flex: 1, width: '100%' }}
                behavior={Platform.OS === 'ios' ? 'padding' : undefined}
            >
                <ScrollView
                    contentContainerStyle={s.scroll}
                    keyboardShouldPersistTaps="handled"
                    showsVerticalScrollIndicator={false}
                >
                    {/* ── Glass Card ───────────────────────────────────── */}
                    <View style={s.card}>

                        {/* Brand */}
                        <View style={s.brandWrap}>
                            <Text style={s.brand}>INDISCAN</Text>
                            <Text style={s.brandSub}>Intelligence Network Access</Text>
                        </View>

                        {/* Error / Success alerts */}
                        {!!errorMsg && (
                            <View style={s.alertError}>
                                <Text style={s.alertErrorTxt}>{errorMsg}</Text>
                            </View>
                        )}
                        {!!successMsg && (
                            <View style={s.alertSuccess}>
                                <Text style={s.alertSuccessTxt}>{successMsg}</Text>
                            </View>
                        )}

                        {/* ── Operational Identity ─────────────────────── */}
                        <Text style={s.label}>OPERATIONAL IDENTITY</Text>
                        <TextInput
                            style={s.input}
                            placeholder="Choose username"
                            placeholderTextColor="#94a3b8"
                            autoCapitalize="none"
                            value={form.username}
                            onChangeText={set('username')}
                        />

                        {/* ── Secure Email ──────────────────────────────── */}
                        <Text style={s.label}>SECURE EMAIL</Text>
                        <TextInput
                            style={s.input}
                            placeholder="agent@indiscan.gov"
                            placeholderTextColor="#94a3b8"
                            autoCapitalize="none"
                            keyboardType="email-address"
                            value={form.email}
                            onChangeText={set('email')}
                        />

                        {/* ── System Key (password) ─────────────────────── */}
                        <Text style={s.label}>SYSTEM KEY</Text>
                        <TextInput
                            style={s.input}
                            placeholder="••••••••"
                            placeholderTextColor="#94a3b8"
                            secureTextEntry
                            value={form.password}
                            onChangeText={set('password')}
                        />
                        {/* Password strength indicator dot */}
                        <View style={s.pwHint}>
                            <View style={[s.dot, pwMet && s.dotMet]} />
                            <Text style={s.pwHintTxt}>Policy: Minimum 6 cryptographic characters</Text>
                        </View>

                        {/* ── Confirm Key ───────────────────────────────── */}
                        <Text style={[s.label, { marginTop: 18 }]}>CONFIRM KEY</Text>
                        <TextInput
                            style={[
                                s.input,
                                form.confirm_password.length > 0 && {
                                    borderColor: form.password === form.confirm_password
                                        ? 'rgba(34,197,94,0.6)'
                                        : 'rgba(239,68,68,0.6)',
                                },
                            ]}
                            placeholder="••••••••"
                            placeholderTextColor="#94a3b8"
                            secureTextEntry
                            value={form.confirm_password}
                            onChangeText={set('confirm_password')}
                        />

                        {/* ── Submit ────────────────────────────────────── */}
                        <TouchableOpacity
                            style={[s.btn, loading && { opacity: 0.7 }]}
                            onPress={handleRegister}
                            disabled={loading}
                        >
                            {loading
                                ? <ActivityIndicator color="#fff" />
                                : <Text style={s.btnTxt}>Request Credentials</Text>}
                        </TouchableOpacity>

                        {/* ── Login link ────────────────────────────────── */}
                        <View style={s.loginLink}>
                            <Text style={s.loginLinkTxt}>Already verified? </Text>
                            <TouchableOpacity onPress={() => navigation.navigate('Login')}>
                                <Text style={s.loginLinkAccent}>Initialize Session</Text>
                            </TouchableOpacity>
                        </View>
                    </View>
                </ScrollView>
            </KeyboardAvoidingView>
        </View>
    );
}

const s = StyleSheet.create({
    bg: {
        flex: 1,
        backgroundColor: '#0f172a',
        alignItems: 'center',
        justifyContent: 'center',
    },

    // Animated blobs
    blob1: {
        position: 'absolute', top: -100, left: -100,
        width: 320, height: 320, borderRadius: 160,
        backgroundColor: 'rgba(168,85,247,0.10)',
    },
    blob2: {
        position: 'absolute', bottom: -100, right: -100,
        width: 320, height: 320, borderRadius: 160,
        backgroundColor: 'rgba(99,102,241,0.10)',
    },

    scroll: {
        flexGrow: 1, justifyContent: 'center', alignItems: 'center', paddingVertical: 32, paddingHorizontal: 20,
    },

    // Glass card (mirrors .glass-card with border-radius 32px)
    card: {
        width: '100%', maxWidth: 480,
        backgroundColor: 'rgba(15,23,42,0.78)',
        borderRadius: 32, borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.10)',
        padding: 36,
        shadowColor: '#000', shadowOpacity: 0.45, shadowRadius: 40, elevation: 16,
    },

    // Brand
    brandWrap: { alignItems: 'center', marginBottom: 28 },
    brand: { fontSize: 30, fontWeight: '800', color: '#a855f7', letterSpacing: 2 },
    brandSub: { color: '#f1f5f9', marginTop: 6, fontSize: 13 },

    // Alerts
    alertError: { backgroundColor: 'rgba(244,63,94,0.12)', borderRadius: 12, padding: 12, marginBottom: 16 },
    alertErrorTxt: { color: '#fb7185', fontSize: 13 },
    alertSuccess: { backgroundColor: 'rgba(34,197,94,0.12)', borderRadius: 12, padding: 12, marginBottom: 16 },
    alertSuccessTxt: { color: '#4ade80', fontSize: 13 },

    // Fields
    label: {
        fontSize: 11, fontWeight: '700', color: '#f1f5f9',
        letterSpacing: 1, textTransform: 'uppercase', marginBottom: 6, marginTop: 16,
    },
    input: {
        backgroundColor: 'rgba(0,0,0,0.30)',
        borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)',
        borderRadius: 12, color: '#fff',
        paddingHorizontal: 18, paddingVertical: 14, fontSize: 14,
    },

    // Password hint
    pwHint: { flexDirection: 'row', alignItems: 'center', marginTop: 8, gap: 8 },
    dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: '#f43f5e' },
    dotMet: { backgroundColor: '#22c55e', shadowColor: '#22c55e', shadowOpacity: 0.6, shadowRadius: 6, elevation: 3 },
    pwHintTxt: { color: '#e2e8f0', fontSize: 11 },

    // Submit button (mirrors btn-register with primary gradient)
    btn: {
        marginTop: 28, borderRadius: 12, paddingVertical: 16,
        backgroundColor: '#7c3aed',
        alignItems: 'center',
        shadowColor: '#a855f7', shadowOpacity: 0.4, shadowRadius: 16, elevation: 8,
    },
    btnTxt: { color: '#fff', fontWeight: '700', fontSize: 15 },

    // Login link (mirrors .login-link with top border)
    loginLink: {
        flexDirection: 'row', justifyContent: 'center', alignItems: 'center',
        marginTop: 28, paddingTop: 20,
        borderTopWidth: 1, borderColor: 'rgba(255,255,255,0.07)',
    },
    loginLinkTxt: { color: '#f1f5f9', fontSize: 13 },
    loginLinkAccent: { color: '#a855f7', fontWeight: '700', fontSize: 13 },
});
