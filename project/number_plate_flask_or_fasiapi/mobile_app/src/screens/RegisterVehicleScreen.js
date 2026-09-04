// screens/RegisterVehicleScreen.js
// Mirrors: /register-vehicle → register_vehicle.html
import React, { useState } from 'react';
import {
    ScrollView, View, Text, TextInput, StyleSheet,
    TouchableOpacity, ActivityIndicator, Alert,
} from 'react-native';
import { apiPost } from '../api';

const VEHICLE_TYPES = ['Petrol', 'Diesel', 'EV', 'CNG', 'Hybrid'];
const VEHICLE_CATEGORIES = ['Bike', 'Car', 'Bus', 'Truck', 'Auto'];

export default function RegisterVehicleScreen({ navigation }) {
    const [form, setForm] = useState({
        vehicle_number: '', owner_name: '', owner_location: '',
        phone_number: '', email: '', vehicle_type: '', vehicle_category: '', vehicle_name: '',
    });
    const [loading, setLoading] = useState(false);
    const set = (k) => (v) => setForm(f => ({ ...f, [k]: v }));

    const handleSubmit = async () => {
        if (!form.vehicle_number.trim()) {
            Alert.alert('Error', 'Vehicle number is required'); return;
        }
        setLoading(true);
        try {
            const data = await apiPost('/api/register-vehicle', {
                ...form,
                vehicle_number: form.vehicle_number.trim().toUpperCase(),
            });
            if (data.success) {
                Alert.alert('Success', data.message, [
                    { text: 'OK', onPress: () => navigation.goBack() },
                ]);
            } else {
                Alert.alert('Error', data.message);
            }
        } catch {
            Alert.alert('Network Error', 'Could not reach server');
        } finally {
            setLoading(false);
        }
    };

    return (
        <ScrollView style={s.bg} contentContainerStyle={s.content}>
            <Text style={s.title}>Register <Text style={s.accent}>Vehicle</Text></Text>

            {/* Vehicle Number (required) */}
            <Text style={s.label}>VEHICLE NUMBER *</Text>
            <TextInput style={s.input} placeholder="e.g. AP10AB1234" placeholderTextColor="#94a3b8"
                autoCapitalize="characters" value={form.vehicle_number} onChangeText={set('vehicle_number')} />

            {/* Owner Details */}
            {[
                { key: 'owner_name', label: 'OWNER NAME', placeholder: 'Full name' },
                { key: 'owner_location', label: 'LOCATION/CITY', placeholder: 'City or District' },
                { key: 'phone_number', label: 'PHONE NUMBER', placeholder: '+91 XXXXXXXXXX' },
                { key: 'email', label: 'EMAIL', placeholder: 'owner@email.com' },
                { key: 'vehicle_name', label: 'VEHICLE MODEL', placeholder: 'e.g. Maruti Swift' },
            ].map(({ key, label, placeholder }) => (
                <View key={key}>
                    <Text style={s.label}>{label}</Text>
                    <TextInput
                        style={s.input} placeholder={placeholder} placeholderTextColor="#94a3b8"
                        autoCapitalize="none" value={form[key]} onChangeText={set(key)}
                    />
                </View>
            ))}

            {/* Vehicle Type Chip selector */}
            <Text style={s.label}>FUEL TYPE</Text>
            <View style={s.chipRow}>
                {VEHICLE_TYPES.map(t => (
                    <TouchableOpacity key={t} style={[s.chip, form.vehicle_type === t && s.chipActive]} onPress={() => set('vehicle_type')(t)}>
                        <Text style={[s.chipText, form.vehicle_type === t && s.chipTextActive]}>{t}</Text>
                    </TouchableOpacity>
                ))}
            </View>

            <Text style={s.label}>VEHICLE CATEGORY</Text>
            <View style={s.chipRow}>
                {VEHICLE_CATEGORIES.map(c => (
                    <TouchableOpacity key={c} style={[s.chip, form.vehicle_category === c && s.chipActive]} onPress={() => set('vehicle_category')(c)}>
                        <Text style={[s.chipText, form.vehicle_category === c && s.chipTextActive]}>{c}</Text>
                    </TouchableOpacity>
                ))}
            </View>

            <TouchableOpacity style={s.btn} onPress={handleSubmit} disabled={loading}>
                {loading ? <ActivityIndicator color="#fff" /> : <Text style={s.btnText}>Register Vehicle</Text>}
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
    title: { fontSize: 22, fontWeight: '800', color: '#fff', marginBottom: 24, marginTop: 10 },
    accent: { color: '#a855f7' },
    label: { fontSize: 10, color: '#94a3b8', fontWeight: '700', letterSpacing: 1.2, marginBottom: 5, marginTop: 14 },
    input: { backgroundColor: 'rgba(0,0,0,0.35)', borderRadius: 12, borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)', color: '#fff', paddingHorizontal: 14, paddingVertical: 13, fontSize: 14 },
    chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 2 },
    chip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, borderWidth: 1, borderColor: 'rgba(255,255,255,0.15)', backgroundColor: 'rgba(255,255,255,0.04)' },
    chipActive: { backgroundColor: '#7c3aed', borderColor: '#a855f7' },
    chipText: { color: '#94a3b8', fontSize: 13 },
    chipTextActive: { color: '#fff', fontWeight: '700' },
    btn: { marginTop: 30, backgroundColor: '#7c3aed', borderRadius: 14, padding: 15, alignItems: 'center', shadowColor: '#a855f7', shadowOpacity: 0.4, shadowRadius: 10, elevation: 5 },
    btnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
    cancelBtn: { marginTop: 12, padding: 14, alignItems: 'center' },
    cancelText: { color: '#64748b', fontSize: 14 },
});
