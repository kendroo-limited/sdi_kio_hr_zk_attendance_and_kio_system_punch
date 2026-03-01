/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class AttendanceDashboard extends Component {
    static template = "kio_system_punch.AttendanceBoard";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.effect = useService("effect");

        this.state = useState({
            employee: null,
            isLoading: false,
            locationInfo: null,
            isCheckedIn: false,
        });

        onWillStart(async () => {
            await this.fetchEmployeeInfo();
        });
    }

    async fetchEmployeeInfo() {
        const result = await this.orm.searchRead(
            "hr.employee",
            [["user_id", "=", this.env.services.user.userId]],
            ["name", "id"],
            { limit: 1 }
        );

        if (result.length > 0) {
            this.state.employee = result[0];
            this.state.employee.image_url = `/web/image?model=hr.employee&id=${this.state.employee.id}&field=image_1920`;
        }
    }

    async onPunchClick() {
        this.state.isLoading = true;
        this.state.locationInfo = null;

        const browser = this.detectBrowser();
        const os_name = this.detectOS();

        const sendRPC = async (lat, long) => {
            try {
                const result = await this.orm.call(
                    "attendance.dashboard",
                    "punch_attendance",
                    [],
                    {
                        lat: lat,
                        long: long,
                        browser: browser,
                        os_name: os_name
                    }
                );

                if (result && result.location_info) {
                    this.state.locationInfo = result.location_info;
                    console.log("Location info received:", result.location_info);
                }

                if (result && result.effect) {
                    this.effect.add(result.effect);
                } else {
                    this.notification.add("Punch recorded successfully!", {
                        type: "success",
                        title: "Success",
                    });
                }
                this.state.isCheckedIn = !this.state.isCheckedIn;
            } catch (error) {
                console.error("Punch error:", error);
                this.notification.add("Failed to punch attendance: " + error.message, {
                    type: "danger",
                    title: "Error",
                });
            } finally {
                this.state.isLoading = false;
            }
        };

        // Check if geolocation is available
        if (!("geolocation" in navigator)) {
            console.warn("Geolocation not supported");
            this.notification.add("Geolocation not supported by your browser.", {
                type: "info",
                title: "Info",
            });
            sendRPC(false, false);
            return;
        }

        // Check permissions first
        try {
            if (navigator.permissions && navigator.permissions.query) {
                const permissionStatus = await navigator.permissions.query({ name: 'geolocation' });
                console.log("Geolocation permission status:", permissionStatus.state);

                if (permissionStatus.state === 'denied') {
                    this.notification.add("Location permission is blocked. Please enable location access in your browser settings and reload the page.", {
                        type: "warning",
                        title: "Location Blocked",
                    });
                    sendRPC(false, false);
                    return;
                }
            }
        } catch (permError) {
            console.log("Permission API not available:", permError);
        }

        // Request geolocation
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude;
                const long = position.coords.longitude;
                console.log("Geolocation obtained:", lat, long);
                sendRPC(lat, long);
            },
            (error) => {
                console.warn("Geolocation error:", error.code, error.message);
                let errorMessage = "Location access failed. ";

                switch(error.code) {
                    case error.PERMISSION_DENIED:
                        errorMessage += "Please allow location access when prompted by your browser.";
                        break;
                    case error.POSITION_UNAVAILABLE:
                        errorMessage += "Location information is unavailable.";
                        break;
                    case error.TIMEOUT:
                        errorMessage += "Location request timed out.";
                        break;
                    default:
                        errorMessage += "Unknown error occurred.";
                }

                this.notification.add(errorMessage + " Proceeding without location.", {
                    type: "warning",
                    title: "Location Warning",
                });
                sendRPC(false, false);
            },
            {
                enableHighAccuracy: false,  // Changed to false for faster response
                timeout: 15000,              // Increased timeout to 15 seconds
                maximumAge: 30000            // Allow cached location up to 30 seconds old
            }
        );
    }

    async onCheckInClick() {
        await this.onPunchClick();
    }

    async onCheckOutClick() {
        await this.onPunchClick();
    }

    detectBrowser() {
        const ua = navigator.userAgent || '';
        if (/Edg/i.test(ua)) return 'Edge';
        if (/CriOS|Chrome/i.test(ua)) return 'Chrome';
        if (/Firefox/i.test(ua)) return 'Firefox';
        if (/FxiOS/i.test(ua)) return 'Firefox-iOS';
        if (/OPR|Opera/i.test(ua)) return 'Opera';
        if (/Safari/i.test(ua) && !/Chrome|CriOS|FxiOS|OPR|Edg/i.test(ua)) return 'Safari';
        return 'Unknown';
    }

    detectOS() {
        const ua = navigator.userAgent || '';
        if (/Android/i.test(ua)) return 'Android';
        if (/iPhone|iPad|iPod/i.test(ua)) return 'iOS';
        if (/Win/i.test(ua)) return 'Windows';
        if (/Mac/i.test(ua) && !/iPhone|iPad|iPod/i.test(ua)) return 'macOS';
        if (/Linux/i.test(ua)) return 'Linux';
        if (/X11/i.test(ua)) return 'UNIX';
        return 'Unknown';
    }
}

registry.category("actions").add("attendance_board", AttendanceDashboard);
