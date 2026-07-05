// static/js/notifications.js

document.addEventListener("DOMContentLoaded", function () {
    const widget = document.querySelector("[data-notification-widget]");
    if (!widget) return;

    const toggleButton = widget.querySelector("[data-notification-toggle]");
    const dropdown = widget.querySelector("[data-notification-dropdown]");
    const badge = widget.querySelector("[data-notification-badge]");
    const list = widget.querySelector("[data-notification-list]");
    const markAllButton = widget.querySelector("[data-notification-mark-all]");

    const SUMMARY_URL = "/admin/api/notifications/summary";
    const MARK_ALL_URL = "/admin/notifications/mark-all-read";

    function escapeHtml(value) {
        if (value === null || value === undefined) return "";
        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    function setBadge(count) {
        if (!badge) return;

        const unreadCount = Number(count || 0);

        if (unreadCount > 0) {
            badge.textContent = unreadCount > 99 ? "99+" : String(unreadCount);
            badge.classList.remove("is-hidden");
        } else {
            badge.textContent = "0";
            badge.classList.add("is-hidden");
        }
    }

    function renderNotifications(notifications) {
        if (!list) return;

        if (!notifications || notifications.length === 0) {
            list.innerHTML = `
                <div class="admin-notification-empty">
                    No notifications yet.
                </div>
            `;
            return;
        }

        list.innerHTML = notifications.map(function (notification) {
            const id = escapeHtml(notification.id);
            const title = escapeHtml(notification.title || "Notification");
            const message = escapeHtml(notification.message || "");
            const createdAt = escapeHtml(notification.created_at || "");
            const targetUrl = escapeHtml(notification.target_url || "/admin/timeline");
            const unreadClass = notification.is_read ? "" : " is-unread";

            return `
                <a class="admin-notification-item${unreadClass}"
                   href="${targetUrl}"
                   data-notification-id="${id}">
                    <span class="admin-notification-title">${title}</span>
                    <span class="admin-notification-message">${message}</span>
                    <span class="admin-notification-time">${createdAt}</span>
                </a>
            `;
        }).join("");
    }

    async function loadNotifications() {
        try {
            const response = await fetch(SUMMARY_URL, {
                method: "GET",
                headers: {
                    "Accept": "application/json"
                },
                credentials: "same-origin"
            });

            if (!response.ok) {
                console.error("Notification summary request failed:", response.status);
                return;
            }

            const data = await response.json();

            setBadge(data.unread_count || 0);
            renderNotifications(data.notifications || []);
        } catch (error) {
            console.error("Notification summary request error:", error);
        }
    }

    async function markNotificationAsRead(notificationId) {
        if (!notificationId) return;

        try {
            await fetch(`/admin/notifications/${notificationId}/read`, {
                method: "POST",
                headers: {
                    "Accept": "application/json"
                },
                credentials: "same-origin"
            });
        } catch (error) {
            console.error("Mark notification as read failed:", error);
        }
    }

    async function markAllAsRead(event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }

        try {
            const response = await fetch(MARK_ALL_URL, {
                method: "POST",
                headers: {
                    "Accept": "application/json"
                },
                credentials: "same-origin"
            });

            if (!response.ok) {
                console.error("Mark all notifications as read failed:", response.status);
                return;
            }

            setBadge(0);

            const unreadItems = widget.querySelectorAll(".admin-notification-item.is-unread");
            unreadItems.forEach(function (item) {
                item.classList.remove("is-unread");
            });

            await loadNotifications();
        } catch (error) {
            console.error("Mark all notifications as read error:", error);
        }
    }

    function openDropdown() {
        if (!dropdown) return;
        dropdown.classList.add("is-open");
        loadNotifications();
    }

    function closeDropdown() {
        if (!dropdown) return;
        dropdown.classList.remove("is-open");
    }

    function toggleDropdown(event) {
        event.preventDefault();
        event.stopPropagation();

        if (!dropdown) return;

        if (dropdown.classList.contains("is-open")) {
            closeDropdown();
        } else {
            openDropdown();
        }
    }

    if (toggleButton) {
        toggleButton.addEventListener("click", toggleDropdown);
    }

    if (markAllButton) {
        markAllButton.addEventListener("click", markAllAsRead);
    }

    if (list) {
        list.addEventListener("click", function (event) {
            const item = event.target.closest("[data-notification-id]");
            if (!item) return;

            const notificationId = item.getAttribute("data-notification-id");
            markNotificationAsRead(notificationId);
        });
    }

    document.addEventListener("click", function (event) {
        if (!widget.contains(event.target)) {
            closeDropdown();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closeDropdown();
        }
    });

    loadNotifications();

    setInterval(loadNotifications, 10000);
});