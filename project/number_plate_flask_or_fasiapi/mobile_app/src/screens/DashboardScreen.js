// screens/DashboardScreen.js
// Faithfully mirrors index.html — glassmorphism theme, 4 tabs,
// result cards with 2-col grid, stolen pulse, plate thumbnails
import React, { useState, useEffect, useRef } from 'react';
import {
    View, Text, TextInput, TouchableOpacity, StyleSheet,
    ScrollView, ActivityIndicator, Alert, Image, Animated,
    SafeAreaView, StatusBar, FlatList, Platform, PermissionsAndroid
} from 'react-native';
import DocumentPicker from 'react-native-document-picker';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Geolocation from '@react-native-community/geolocation';
import { apiPost, apiUpload } from '../api';

// ── Stolen pulse animation component ────────────────────────────────────────
function StolenPulse({ children, stolen }) {
    const pulse = useRef(new Animated.Value(0)).current;
    useEffect(() => {
        if (!stolen) return;
        const anim = Animated.loop(
            Animated.sequence([
                Animated.timing(pulse, { toValue: 1, duration: 700, useNativeDriver: false }),
                Animated.timing(pulse, { toValue: 0, duration: 700, useNativeDriver: false }),
            ])
        );
        anim.start();
        return () => anim.stop();
    }, [stolen]);

    const borderColor = stolen
        ? pulse.interpolate({ inputRange: [0, 1], outputRange: ['rgba(244,63,94,0.3)', 'rgba(244,63,94,0.9)'] })
        : 'rgba(255,255,255,0.1)';

    return (
        <Animated.View style={[s.glassCard, stolen && s.stolenCard, { borderColor }]}>
            {children}
        </Animated.View>
    );
}

// ── Vehicle detail 2×2 grid ─────────────────────────────────────────────────
function DetailsGrid({ d }) {
    const items = [
        ['Registered Owner', d?.owner_name],
        ['Mobile Number', d?.phone_number],
        ['Vehicle Model', d?.vehicle_name],
        ['Fuel / Type', d?.vehicle_type],
        ['Registration Hub', d?.owner_location],
        ['Category', d?.vehicle_category],
    ];
    return (
        <View style={s.detailsGrid}>
            {items.map(([lbl, val]) => (
                <View key={lbl} style={s.detailsItem}>
                    <Text style={s.detailsLabel}>{lbl.toUpperCase()}</Text>
                    <Text style={s.detailsVal}>{val || '—'}</Text>
                </View>
            ))}
        </View>
    );
}

// ── Single detected plate card (mirrors list-group-item in index.html) ──────
function PlateCard({ plate, info, onRegister }) {
    const [expanded, setExpanded] = useState(false);
    return (
        <StolenPulse stolen={info.is_stolen}>
            {/* Row: thumb + plate + badge */}
            <View style={s.plateRow}>
                {info.img_base64 ? (
                    <Image
                        source={{ uri: `data:image/jpeg;base64,${info.img_base64}` }}
                        style={s.plateThumb}
                    />
                ) : null}
                <View style={{ flex: 1 }}>
                    <View style={s.rowBetween}>
                        <Text style={s.plateTxt}>{plate}</Text>
                        <View style={[s.badge, info.is_stolen ? s.badgeDanger : s.badgeSafe]}>
                            <Text style={s.badgeTxt}>{info.is_stolen ? '🚨 STOLEN' : '✓ SAFE'}</Text>
                        </View>
                    </View>
                    <View style={s.rowGap}>
                        <View style={s.tagDark}>
                            <Text style={s.tagTxt}>{info.db_status === 'found' ? '✓ Registered' : '? Unknown'}</Text>
                        </View>
                        {info.state ? <Text style={s.stateTxt}>{info.state}</Text> : null}
                    </View>
                </View>
            </View>

            {/* Stolen warning banner */}
            {info.is_stolen && (
                <View style={s.stolenBanner}>
                    <Text style={{ fontSize: 24, marginRight: 8 }}>🚨</Text>
                    <View>
                        <Text style={s.stolenBannerTitle}>CRITICAL MATCH FOUND</Text>
                        <Text style={s.stolenBannerTxt}>Vehicle marked as stolen.</Text>
                    </View>
                </View>
            )}

            {/* Action buttons */}
            <View style={s.actionRow}>
                {info.vehicle_details ? (
                    <TouchableOpacity style={s.outlineBtn} onPress={() => setExpanded(e => !e)}>
                        <Text style={s.outlineTxt}>{expanded ? 'Hide' : 'Details'}</Text>
                    </TouchableOpacity>
                ) : (
                    <TouchableOpacity style={s.outlineBtn} onPress={onRegister}>
                        <Text style={s.outlineTxt}>Register</Text>
                    </TouchableOpacity>
                )}
            </View>

            {/* Expanded details grid */}
            {expanded && info.vehicle_details && (
                <DetailsGrid d={info.vehicle_details} />
            )}

            {/* Not in db fallback */}
            {!info.vehicle_details && (
                <View style={s.notRegisteredBox}>
                    <Text style={s.warningTxt}>⚠ Not in Database</Text>
                    <TouchableOpacity style={s.miniBtn} onPress={onRegister}>
                        <Text style={s.miniBtnTxt}>Register Now</Text>
                    </TouchableOpacity>
                </View>
            )}
        </StolenPulse>
    );
}

export default function DashboardScreen({ navigation }) {
    const [username, setUsername] = useState('User');
    const [userEmail, setUserEmail] = useState('');
    const [tab, setTab] = useState('photo'); // 'photo' | 'video' | 'live' | 'search'
    const [loading, setLoading] = useState(false);
    const [location, setLocation] = useState({ lat: null, lon: null });

    // ── Upload handler ─────────────────────────────────────────────────────────
    const handleUpload = async (mediaType) => {
        if (!location.lat || !location.lon) {
            Alert.alert(
                'Location Required',
                'Your exact GPS location is required to use this scanner. Please enable location services and try again.'
            );
            return;
        }

        try {
            const file = await DocumentPicker.pickSingle({
                type: mediaType === 'image'
                    ? [DocumentPicker.types.images]
                    : [DocumentPicker.types.video],
            });
            setLoading(true);
            setUploadResults([]);

            const fd = new FormData();
            fd.append('media_type', mediaType);
            fd.append('file', { uri: file.uri, name: file.name, type: file.type });

            if (location.lat && location.lon) {
                fd.append('latitude', location.lat);
                fd.append('longitude', location.lon);
            }
            if (username && username !== 'User') {
                fd.append('officer_username', username);
            }
            if (userEmail) {
                fd.append('officer_email', userEmail);
            }

            const data = await apiUpload('/api/upload', fd);
            setUploadResults(Array.isArray(data) ? data : []);
        } catch (e) {
            if (!DocumentPicker.isCancel(e)) Alert.alert('Error', 'Upload failed');
        } finally {
            setLoading(false);
        }
    };

    // Photo/Video upload state
    const [uploadResults, setUploadResults] = useState([]);

    // Search state
    const [searchPlate, setSearchPlate] = useState('');
    const [searchResult, setSearchResult] = useState(null);
    const [searchLoading, setSearchLoading] = useState(false);

    useEffect(() => {
        AsyncStorage.getItem('username').then(u => { if (u) setUsername(u); });
        AsyncStorage.getItem('user_email').then(e => { if (e) setUserEmail(e); });

        let watchId = null;

        const startWatching = () => {
            watchId = Geolocation.watchPosition(
                (info) => {
                    setLocation({
                        lat: info.coords.latitude.toString(),
                        lon: info.coords.longitude.toString()
                    });
                },
                (err) => console.log('GPS Error', err),
                { enableHighAccuracy: true, timeout: 20000, maximumAge: 1000 }
            );
        };

        const requestLocationPermission = async () => {
            if (Platform.OS === 'android') {
                try {
                    const granted = await PermissionsAndroid.request(
                        PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION,
                        {
                            title: 'IndiScan Location Permission',
                            message: 'IndiScan needs access to your location to report accurate scanner data to the central database.',
                            buttonNeutral: 'Ask Me Later',
                            buttonNegative: 'Cancel',
                            buttonPositive: 'OK',
                        }
                    );
                    if (granted === PermissionsAndroid.RESULTS.GRANTED) {
                        startWatching();
                    } else {
                        console.log('Location permission denied');
                    }
                } catch (err) {
                    console.warn(err);
                }
            } else {
                Geolocation.requestAuthorization();
                startWatching();
            }
        };

        requestLocationPermission();

        return () => {
            if (watchId !== null) Geolocation.clearWatch(watchId);
        };
    }, []);

    const logout = async () => {
        await AsyncStorage.multiRemove(['user_id', 'username']);
        navigation.replace('Login');
    };

    // ── Search handler ─────────────────────────────────────────────────────────
    const handleSearch = async () => {
        const plate = searchPlate.trim().toUpperCase();
        if (!plate) return;
        setSearchLoading(true);
        setSearchResult(null);
        try {
            const data = await apiPost('/api/check-plate', { number_plate: plate });
            setSearchResult({ ...data, queriedPlate: plate });
        } catch {
            Alert.alert('Error', 'Network request failed');
        } finally {
            setSearchLoading(false);
        }
    };

    // ── Render search result card ──────────────────────────────────────────────
    const renderSearchResult = () => {
        if (!searchResult) return null;
        const plate = searchResult.queriedPlate;
        if (searchResult.found) {
            return (
                <StolenPulse stolen={searchResult.is_stolen}>
                    <View style={s.rowBetween}>
                        <Text style={s.plateTxt}>{plate}</Text>
                        <View style={[s.badge, searchResult.is_stolen ? s.badgeDanger : s.badgeSafe]}>
                            <Text style={s.badgeTxt}>{searchResult.is_stolen ? '🚨 STOLEN' : '✓ SECURE'}</Text>
                        </View>
                    </View>
                    <DetailsGrid d={searchResult.data} />
                </StolenPulse>
            );
        }
        return (
            <View style={[s.glassCard, { borderColor: 'rgba(234,179,8,0.4)' }]}>
                <Text style={s.notFoundTitle}>No Record Found</Text>
                <Text style={s.muted}>The plate <Text style={{ color: '#fff' }}>{plate}</Text> does not match any registered vehicle.</Text>
                <TouchableOpacity style={[s.btn, { marginTop: 14 }]} onPress={() => navigation.navigate('RegisterVehicle')}>
                    <Text style={s.btnTxt}>Register Now</Text>
                </TouchableOpacity>
            </View>
        );
    };

    // ── Render upload result cards ─────────────────────────────────────────────
    const renderUploadResults = () => uploadResults.map((result, i) => (
        <View key={i} style={[s.glassCard, { padding: 0, overflow: 'hidden' }]}>
            {/* Header */}
            <View style={s.resultHeader}>
                <Text style={s.resultHeaderTxt}>
                    <Text style={{ color: '#fff' }}>Analysis: </Text>
                    <Text style={{ color: '#94a3b8' }}>{result.filename}</Text>
                </Text>
            </View>
            <View style={{ padding: 16 }}>
                {/* Processed image */}
                {result.type === 'image' && result.main_img && (
                    <Image
                        source={{ uri: `data:image/jpeg;base64,${result.main_img}` }}
                        style={s.mainImg}
                    />
                )}
                {result.type === 'video' && (
                    <View style={[s.glassCard, { alignItems: 'center', padding: 24 }]}>
                        <Text style={{ color: '#a855f7', fontWeight: '700', fontSize: 15, marginBottom: 6 }}>Video Stream Processed</Text>
                        <Text style={s.muted}>Sequential frame analysis completed.</Text>
                    </View>
                )}
                {/* Detection list */}
                <Text style={s.detectionTitle}>Detections</Text>
                {Object.keys(result.plates || {}).length === 0
                    ? <View style={[s.glassCard, { alignItems: 'center', padding: 20 }]}>
                        <Text style={s.muted}>No intelligence detected</Text>
                    </View>
                    : Object.entries(result.plates).map(([plate, info]) => (
                        <PlateCard
                            key={plate}
                            plate={plate}
                            info={info}
                            onRegister={() => navigation.navigate('RegisterVehicle')}
                        />
                    ))
                }
            </View>
        </View>
    ));

    const TABS = [
        { key: 'photo', label: 'Photos' },
        { key: 'video', label: 'Videos' },
        { key: 'live', label: 'Live Cam' },
        { key: 'search', label: 'Search' },
    ];

    return (
        <SafeAreaView style={s.bg}>
            <StatusBar barStyle="light-content" backgroundColor="#0f172a" />

            {/* ── Navbar (mirrors glass-nav) ────────────────────────────────── */}
            <View style={s.navbar}>
                <Text style={s.brand}>INDISCAN</Text>
                <View style={s.navRight}>
                    <Text style={s.navHello}>Hello, <Text style={s.accent}>{username}</Text></Text>
                    <TouchableOpacity style={s.navLink} onPress={() => navigation.navigate('RegisterVehicle')}>
                        <Text style={s.navLinkTxt}>Register Vehicle</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={s.navLink} onPress={() => navigation.navigate('Complaint')}>
                        <Text style={s.navLinkTxt}>Complaints</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={s.logoutBtn} onPress={logout}>
                        <Text style={s.logoutTxt}>Logout</Text>
                    </TouchableOpacity>
                </View>
            </View>

            <ScrollView contentContainerStyle={s.content}>

                {/* ── Page title ──────────────────────────────────────────────── */}
                <Text style={s.pageTitle}>
                    AI Powered {'\n'}<Text style={s.titleAccent}>LPR Dashboard</Text>
                </Text>

                {/* ── Tab card (mirrors glass-card with nav-pills) ─────────────── */}
                <View style={s.glassCard}>
                    {/* Tab bar */}
                    <View style={s.tabBar}>
                        {TABS.map(t => (
                            <TouchableOpacity
                                key={t.key}
                                style={[s.tabBtn, tab === t.key && s.tabActive]}
                                onPress={() => setTab(t.key)}
                            >
                                <Text style={[s.tabTxt, tab === t.key && s.tabTxtActive]}>{t.label}</Text>
                            </TouchableOpacity>
                        ))}
                    </View>

                    {/* ── Photos tab ────────────────────────────────────────────── */}
                    {tab === 'photo' && (
                        <View style={s.tabContent}>
                            <Text style={[s.muted, { textAlign: 'center', marginBottom: 16 }]}>
                                Upload one or more vehicle images for batch recognition.
                            </Text>
                            <TouchableOpacity
                                style={s.btn}
                                onPress={() => handleUpload('image')}
                                disabled={loading}
                            >
                                {loading
                                    ? <ActivityIndicator color="#fff" />
                                    : <Text style={s.btnTxt}>Execute Batch Recognition</Text>}
                            </TouchableOpacity>
                        </View>
                    )}

                    {/* ── Videos tab ────────────────────────────────────────────── */}
                    {tab === 'video' && (
                        <View style={s.tabContent}>
                            <Text style={[s.muted, { textAlign: 'center', marginBottom: 16 }]}>
                                Select a video file. Our AI will sample frames periodically.
                            </Text>
                            <TouchableOpacity
                                style={s.btn}
                                onPress={() => handleUpload('video')}
                                disabled={loading}
                            >
                                {loading
                                    ? <ActivityIndicator color="#fff" />
                                    : <Text style={s.btnTxt}>Process Video Stream</Text>}
                            </TouchableOpacity>
                        </View>
                    )}

                    {/* ── Live Cam tab ───────────────────────────────────────────── */}
                    {tab === 'live' && (
                        <View style={s.tabContent}>
                            <View style={s.livePlaceholder}>
                                <Text style={{ fontSize: 32, marginBottom: 10 }}>📷</Text>
                                <Text style={s.livePlaceholderTitle}>Live Detection</Text>
                                <Text style={[s.muted, { textAlign: 'center' }]}>
                                    Live camera detection is available in the desktop version.{'\n'}
                                    Use the Photos tab to upload captured images.
                                </Text>
                            </View>
                        </View>
                    )}

                    {/* ── Search tab ────────────────────────────────────────────── */}
                    {tab === 'search' && (
                        <View style={s.tabContent}>
                            <View style={s.searchRow}>
                                <TextInput
                                    style={[s.input, { flex: 1 }]}
                                    placeholder="Enter plate number (e.g., AP 10 AB 1234)"
                                    placeholderTextColor="#94a3b8"
                                    autoCapitalize="characters"
                                    value={searchPlate}
                                    onChangeText={setSearchPlate}
                                    onSubmitEditing={handleSearch}
                                />
                                <TouchableOpacity style={s.searchBtn} onPress={handleSearch} disabled={searchLoading}>
                                    {searchLoading
                                        ? <ActivityIndicator color="#fff" size="small" />
                                        : <Text style={s.btnTxt}>Search</Text>}
                                </TouchableOpacity>
                            </View>
                            {renderSearchResult()}
                        </View>
                    )}
                </View>

                {/* ── Neural engine loader ────────────────────────────────────── */}
                {loading && (
                    <View style={s.loaderBox}>
                        <ActivityIndicator color="#a855f7" size="large" />
                        <Text style={[s.muted, { marginTop: 10 }]}>Neural engine processing frames...</Text>
                    </View>
                )}

                {/* ── Upload results ─────────────────────────────────────────── */}
                {renderUploadResults()}
            </ScrollView>
        </SafeAreaView>
    );
}

// ─── Styles ─────────────────────────────────────────────────────────────────
const PURPLE = '#a855f7';
const PURPLE_D = '#7c3aed';
const BG = '#0f172a';
const GLASS = 'rgba(255,255,255,0.05)';
const BORDER = 'rgba(255,255,255,0.1)';

const s = StyleSheet.create({
    bg: { flex: 1, backgroundColor: BG },

    // Navbar
    navbar: { backgroundColor: 'rgba(15,23,42,0.95)', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderColor: BORDER },
    brand: { fontSize: 20, fontWeight: '800', color: PURPLE, letterSpacing: 2, marginBottom: 8 },
    navRight: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 8 },
    navHello: { color: '#f1f5f9', fontSize: 12 },
    accent: { color: PURPLE, fontWeight: '700' },
    navLink: { paddingHorizontal: 10, paddingVertical: 4 },
    navLinkTxt: { color: '#f1f5f9', fontSize: 12 },
    logoutBtn: { borderWidth: 1, borderColor: '#dc2626', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 4 },
    logoutTxt: { color: '#dc2626', fontSize: 12, fontWeight: '600' },

    content: { padding: 16, paddingBottom: 40 },

    // Page title
    pageTitle: { fontSize: 22, fontWeight: '700', color: '#fff', textAlign: 'center', letterSpacing: -0.4, marginVertical: 20 },
    titleAccent: { color: PURPLE },

    // Tab card
    glassCard: { backgroundColor: GLASS, borderRadius: 20, borderWidth: 1, borderColor: BORDER, marginBottom: 14, padding: 16, shadowColor: '#1f2687', shadowOpacity: 0.37, shadowRadius: 20, elevation: 8 },
    stolenCard: { backgroundColor: 'rgba(244,63,94,0.15)', borderWidth: 2, borderColor: '#f43f5e' },

    tabBar: { flexDirection: 'row', backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: 14, padding: 4, marginBottom: 16, gap: 2 },
    tabBtn: { flex: 1, paddingVertical: 10, alignItems: 'center', borderRadius: 10 },
    tabActive: { backgroundColor: PURPLE_D, shadowColor: PURPLE, shadowOpacity: 0.4, shadowRadius: 8, elevation: 4 },
    tabTxt: { color: '#f1f5f9', fontSize: 12, fontWeight: '500' },
    tabTxtActive: { color: '#fff', fontWeight: '700' },
    tabContent: { paddingTop: 4 },

    muted: { color: '#f1f5f9', fontSize: 13 },

    // Buttons
    btn: { backgroundColor: PURPLE_D, borderRadius: 12, padding: 14, alignItems: 'center', shadowColor: PURPLE, shadowOpacity: 0.35, shadowRadius: 10, elevation: 5 },
    btnTxt: { color: '#fff', fontWeight: '600', fontSize: 14 },
    outlineBtn: { borderWidth: 1, borderColor: 'rgba(99,102,241,0.6)', borderRadius: 8, paddingVertical: 6, paddingHorizontal: 14, alignSelf: 'flex-start' },
    outlineTxt: { color: '#818cf8', fontSize: 12 },
    miniBtn: { backgroundColor: PURPLE_D, borderRadius: 8, paddingVertical: 6, paddingHorizontal: 14, marginTop: 6, alignSelf: 'stretch', alignItems: 'center' },
    miniBtnTxt: { color: '#fff', fontSize: 12, fontWeight: '600' },

    // Search row
    searchRow: { flexDirection: 'row', gap: 8, marginBottom: 14 },
    input: { backgroundColor: 'rgba(0,0,0,0.2)', borderWidth: 1, borderColor: BORDER, borderRadius: 12, color: '#fff', paddingHorizontal: 14, paddingVertical: 12, fontSize: 13 },
    searchBtn: { backgroundColor: PURPLE_D, borderRadius: 12, paddingHorizontal: 16, justifyContent: 'center', alignItems: 'center' },

    // Live cam placeholder
    livePlaceholder: { alignItems: 'center', paddingVertical: 32 },
    livePlaceholderTitle: { color: '#fff', fontWeight: '700', fontSize: 16, marginBottom: 8 },

    // Loader
    loaderBox: { alignItems: 'center', marginVertical: 24 },

    // Result cards
    resultHeader: { backgroundColor: 'rgba(255,255,255,0.03)', padding: 12, borderBottomWidth: 1, borderColor: BORDER },
    resultHeaderTxt: { fontSize: 13 },
    mainImg: { width: '100%', height: 180, borderRadius: 16, resizeMode: 'contain', marginBottom: 14 },
    detectionTitle: { color: '#fff', fontWeight: '700', fontSize: 15, marginBottom: 10 },

    // Plate card
    plateRow: { flexDirection: 'row', gap: 12, marginBottom: 10 },
    plateThumb: { width: 85, height: 50, borderRadius: 8, borderWidth: 1, borderColor: BORDER, resizeMode: 'contain' },
    plateTxt: { color: '#fff', fontWeight: '800', fontSize: 18 },
    rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
    rowGap: { flexDirection: 'row', gap: 8, alignItems: 'center' },
    tagDark: { backgroundColor: 'rgba(0,0,0,0.3)', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
    tagTxt: { color: '#94a3b8', fontSize: 10 },
    stateTxt: { color: '#94a3b8', fontSize: 10 },
    badge: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 20, shadowColor: '#000', shadowOpacity: 0.2, shadowRadius: 4, elevation: 2 },
    badgeSafe: { backgroundColor: 'rgba(34,197,94,0.2)' },
    badgeDanger: { backgroundColor: '#e11d48' },
    badgeTxt: { color: '#fff', fontSize: 12, fontWeight: '800', letterSpacing: 0.5 },

    stolenBanner: { flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(220,53,69,0.25)', borderRadius: 12, padding: 12, marginBottom: 12, borderWidth: 1, borderColor: 'rgba(244,63,94,0.3)' },
    stolenBannerTitle: { color: '#fff', fontSize: 13, fontWeight: '800', letterSpacing: 0.5, marginBottom: 2 },
    stolenBannerTxt: { color: '#ff8e98', fontSize: 11, fontWeight: '600' },

    actionRow: { flexDirection: 'row', gap: 8, marginBottom: 8 },

    notRegisteredBox: { marginTop: 8, padding: 12, backgroundColor: 'rgba(234,179,8,0.08)', borderRadius: 10, borderWidth: 1, borderColor: 'rgba(234,179,8,0.25)' },
    warningTxt: { color: '#eab308', fontSize: 12, fontWeight: '600', marginBottom: 4 },

    // Details grid  (2-col)
    detailsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 10 },
    detailsItem: { width: '47%', backgroundColor: 'rgba(0,0,0,0.2)', padding: 10, borderRadius: 10 },
    detailsLabel: { color: '#f1f5f9', fontSize: 9, fontWeight: '700', letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 2 },
    detailsVal: { color: '#fff', fontSize: 12 },

    // Search result
    notFoundTitle: { color: '#eab308', fontWeight: '700', fontSize: 15, marginBottom: 8 },
});
