// screens/LoginScreen.js
// Mirrors: /login → login.html  (dark glassmorphism, indigo-purple gradient)
import React, { useState } from 'react';
import {
    View, Text, TextInput, TouchableOpacity, StyleSheet,
    ActivityIndicator, KeyboardAvoidingView, Platform, Alert,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { apiPost } from '../api';

export default function LoginScreen({ navigation }) {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);

    const handleLogin = async () => {
        if (!username.trim() || !password.trim()) {
            Alert.alert('Error', 'Username and password are required');
            return;
        }
        setLoading(true);
        try {
            const data = await apiPost('/api/login', { username, password });
            if (data.success) {
                await AsyncStorage.setItem('user_id', data.user_id);
                await AsyncStorage.setItem('username', data.username);
                await AsyncStorage.setItem('user_email', data.email || '');
                navigation.replace('Dashboard');
            } else {
                Alert.alert('Login Failed', data.message || 'Invalid credentials');
            }
        } catch (e) {
            Alert.alert('Network Error', 'Could not reach the server. Check your ngrok URL.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <KeyboardAvoidingView style={s.bg} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
            <View style={s.card}>
                {/* Brand */}
                <Text style={s.brand}>INDISCAN</Text>
                <Text style={s.sub}>Authentication Gateway</Text>

                {/* Fields */}
                <Text style={s.label}>ACCESS IDENTITY</Text>
                <TextInput
                    style={s.input}
                    placeholder="Enter username"
                    placeholderTextColor="#94a3b8"
                    autoCapitalize="none"
                    value={username}
                    onChangeText={setUsername}
                />

                <Text style={s.label}>SYSTEM KEY</Text>
                <TextInput
                    style={s.input}
                    placeholder="••••••••"
                    placeholderTextColor="#94a3b8"
                    secureTextEntry
                    value={password}
                    onChangeText={setPassword}
                />

                {/* Submit */}
                <TouchableOpacity style={s.btn} onPress={handleLogin} disabled={loading}>
                    {loading
                        ? <ActivityIndicator color="#fff" />
                        : <Text style={s.btnText}>Establish Connection</Text>}
                </TouchableOpacity>

                {/* Link to Register */}
                <TouchableOpacity onPress={() => navigation.navigate('Register')}>
                    <Text style={s.link}>No account? <Text style={s.linkAccent}>Request Credentials</Text></Text>
                </TouchableOpacity>
            </View>
        </KeyboardAvoidingView>
    );
}

const s = StyleSheet.create({
    bg: {
        flex: 1, backgroundColor: '#0f172a',
        justifyContent: 'center', alignItems: 'center', padding: 20,
    },
    card: {
        width: '100%', maxWidth: 420,
        backgroundColor: 'rgba(15,23,42,0.85)',
        borderRadius: 28, padding: 32,
        borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
        shadowColor: '#000', shadowOpacity: 0.5, shadowRadius: 30, elevation: 12,
    },
    brand: {
        fontSize: 28, fontWeight: '800', textAlign: 'center',
        color: '#a855f7', letterSpacing: 2, marginBottom: 4,
    },
    sub: { color: '#94a3b8', textAlign: 'center', marginBottom: 28 },
    label: {
        fontSize: 10, fontWeight: '700', color: '#94a3b8',
        letterSpacing: 1.2, marginBottom: 6, marginTop: 14,
    },
    input: {
        backgroundColor: 'rgba(0,0,0,0.35)', borderRadius: 12,
        borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)',
        color: '#fff', paddingHorizontal: 16, paddingVertical: 13, fontSize: 15,
    },
    btn: {
        marginTop: 24, borderRadius: 14, paddingVertical: 15,
        backgroundColor: '#7c3aed', alignItems: 'center',
        shadowColor: '#a855f7', shadowOpacity: 0.5, shadowRadius: 12, elevation: 6,
    },
    btnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
    link: { color: '#94a3b8', textAlign: 'center', marginTop: 20, fontSize: 13 },
    linkAccent: { color: '#a855f7', fontWeight: '600' },
});
