// screens/ComplaintScreen.js
// Mirrors: /complaint → complaint.html
import React, { useState } from 'react';
import {
    View, Text, TextInput, StyleSheet, TouchableOpacity,
    ActivityIndicator, Alert, ScrollView,
} from 'react-native';
import { apiPost } from '../api';

export default function ComplaintScreen({ navigation }) {
    const [vehicleNumber, setVehicleNumber] = useState('');
    const [action, setAction] = useState('mark_stolen'); // or 'mark_safe'
    const [loading, setLoading] = useState(false);

    const handleSubmit = async () => {
        if (!vehicleNumber.trim()) {
            Alert.alert('Error', 'Vehicle number is required'); return;
        }
        setLoading(true);
        try {
            const data = await apiPost('/api/complaint', {
                vehicle_number: vehicleNumber.trim().toUpperCase(),
                action,
            });
            if (data.success) {
                Alert.alert('Success', data.message, [
                    { text: 'OK', onPress: () => navigation.goBack() },
                ]);
            } else {
                Alert.alert('Not Found', data.message);
            }
        } catch {
            Alert.alert('Network Error', 'Could not reach server');
        } finally {
            setLoading(false);
        }
    };

    return (
        <ScrollView style={s.bg} contentContainerStyle={s.content}>
            <Text style={s.title}>Vehicle <Text style={s.accent}>Complaint</Text></Text>
            <Text style={s.sub}>Report a vehicle as stolen or mark it safe again.</Text>

            <Text style={s.label}>VEHICLE NUMBER</Text>
            <TextInput
                style={s.input}
                placeholder="e.g. AP10AB1234"
                placeholderTextColor="#94a3b8"
                autoCapitalize="characters"
                value={vehicleNumber}
                onChangeText={setVehicleNumber}
            />

            <Text style={s.label}>ACTION</Text>
            <View style={s.toggleRow}>
                <TouchableOpacity
                    style={[s.toggleBtn, action === 'mark_stolen' && s.dangerActive]}
                    onPress={() => setAction('mark_stolen')}
                >
                    <Text style={s.toggleText}>🚨 Mark as Stolen</Text>
                </TouchableOpacity>
                <TouchableOpacity
                    style={[s.toggleBtn, action === 'mark_safe' && s.safeActive]}
                    onPress={() => setAction('mark_safe')}
                >
                    <Text style={s.toggleText}>✓ Mark as Safe</Text>
                </TouchableOpacity>
            </View>

            {action === 'mark_stolen' && (
                <View style={s.warningBox}>
                    <Text style={s.warningText}>
                        ⚠️ This will flag the vehicle in the national database. Law enforcement will be alerted.
                    </Text>
                </View>
            )}

            <TouchableOpacity
                style={[s.btn, action === 'mark_stolen' ? s.dangerBtn : s.safeBtn]}
                onPress={handleSubmit}
                disabled={loading}
            >
                {loading
                    ? <ActivityIndicator color="#fff" />
                    : <Text style={s.btnText}>{action === 'mark_stolen' ? 'Report Stolen' : 'Mark Safe'}</Text>}
            </TouchableOpacity>

            <TouchableOpacity style={s.cancelBtn} onPress={() => navigation.goBack()}>
                <Text style={s.cancelText}>Cancel</Text>
            </TouchableOpacity>
        </ScrollView>
    );
}

const s = StyleSheet.create({
    bg: { flex: 1, backgroundColor: '#0f172a' },
    content: { padding: 24 },
    title: { fontSize: 22, fontWeight: '800', color: '#fff', marginBottom: 6, marginTop: 10 },
    accent: { color: '#a855f7' },
    sub: { color: '#94a3b8', marginBottom: 24, lineHeight: 18 },
    label: { fontSize: 10, color: '#94a3b8', fontWeight: '700', letterSpacing: 1.2, marginBottom: 5, marginTop: 14 },
    input: { backgroundColor: 'rgba(0,0,0,0.35)', borderRadius: 12, borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)', color: '#fff', paddingHorizontal: 14, paddingVertical: 13, fontSize: 14 },
    toggleRow: { flexDirection: 'row', gap: 10, marginTop: 4 },
    toggleBtn: { flex: 1, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)', backgroundColor: 'rgba(255,255,255,0.04)', alignItems: 'center' },
    dangerActive: { backgroundColor: 'rgba(239,68,68,0.15)', borderColor: 'rgba(239,68,68,0.5)' },
    safeActive: { backgroundColor: 'rgba(34,197,94,0.15)', borderColor: 'rgba(34,197,94,0.5)' },
    toggleText: { color: '#e2e8f0', fontWeight: '600', fontSize: 13 },
    warningBox: { marginTop: 16, padding: 14, backgroundColor: 'rgba(239,68,68,0.1)', borderRadius: 12, borderWidth: 1, borderColor: 'rgba(239,68,68,0.3)' },
    warningText: { color: '#fca5a5', fontSize: 12, lineHeight: 18 },
    btn: { marginTop: 28, borderRadius: 14, padding: 15, alignItems: 'center', shadowOpacity: 0.4, shadowRadius: 10, elevation: 5 },
    dangerBtn: { backgroundColor: '#dc2626', shadowColor: '#ef4444' },
    safeBtn: { backgroundColor: '#16a34a', shadowColor: '#22c55e' },
    btnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
    cancelBtn: { marginTop: 12, padding: 14, alignItems: 'center' },
    cancelText: { color: '#64748b', fontSize: 14 },
});
