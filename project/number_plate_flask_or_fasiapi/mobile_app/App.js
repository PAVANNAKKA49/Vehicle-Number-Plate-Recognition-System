// App.js — Main entry point with React Navigation Stack Navigator
// Mirrors all 5 Flask web routes:
//   /login           → LoginScreen
//   /register        → RegisterScreen
//   /                → DashboardScreen   (auth-gated)
//   /register-vehicle → RegisterVehicleScreen
//   /complaint        → ComplaintScreen

import React, { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { ActivityIndicator, View, StatusBar } from 'react-native';

import LoginScreen from './src/screens/LoginScreen';
import RegisterScreen from './src/screens/RegisterScreen';
import DashboardScreen from './src/screens/DashboardScreen';
import RegisterVehicleScreen from './src/screens/RegisterVehicleScreen';
import ComplaintScreen from './src/screens/ComplaintScreen';

const Stack = createNativeStackNavigator();

export default function App() {
    const [isLoggedIn, setIsLoggedIn] = useState(null); // null = loading

    useEffect(() => {
        AsyncStorage.getItem('user_id').then(id => setIsLoggedIn(!!id));
    }, []);

    // Splash / loading state
    if (isLoggedIn === null) {
        return (
            <View style={{ flex: 1, backgroundColor: '#0f172a', justifyContent: 'center', alignItems: 'center' }}>
                <ActivityIndicator size="large" color="#a855f7" />
            </View>
        );
    }

    return (
        <NavigationContainer>
            <StatusBar barStyle="light-content" backgroundColor="#0f172a" />
            <Stack.Navigator
                initialRouteName={isLoggedIn ? 'Dashboard' : 'Login'}
                screenOptions={{
                    headerStyle: { backgroundColor: '#0f172a' },
                    headerTintColor: '#a855f7',
                    headerTitleStyle: { fontWeight: '700', color: '#fff' },
                    headerShadowVisible: false,
                    contentStyle: { backgroundColor: '#0f172a' },
                }}
            >
                {/* Auth Screens (no header needed) */}
                <Stack.Screen
                    name="Login"
                    component={LoginScreen}
                    options={{ headerShown: false }}
                />
                <Stack.Screen
                    name="Register"
                    component={RegisterScreen}
                    options={{ headerShown: false }}
                />

                {/* Main App Screens */}
                <Stack.Screen
                    name="Dashboard"
                    component={DashboardScreen}
                    options={{ headerShown: false }}
                />
                <Stack.Screen
                    name="RegisterVehicle"
                    component={RegisterVehicleScreen}
                    options={{ title: 'Register Vehicle' }}
                />
                <Stack.Screen
                    name="Complaint"
                    component={ComplaintScreen}
                    options={{ title: 'Vehicle Complaint' }}
                />
            </Stack.Navigator>
        </NavigationContainer>
    );
}
