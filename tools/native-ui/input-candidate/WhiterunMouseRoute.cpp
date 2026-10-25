#include "Hooks/WhiterunMouseRoute.h"

namespace NL::Input
{
    WhiterunMouseRoute::WhiterunMouseRoute(std::shared_ptr<spdlog::logger> logger) : m_logger(std::move(logger))
    {
        char value[32]{};
        const auto length = GetEnvironmentVariableA("WHITERUN_UI_INPUT_MODE", value, sizeof(value));
        if (length > 0 && length < sizeof(value)) m_mode = ParseMode(value);
    }
    WhiterunMouseRoute::~WhiterunMouseRoute()
    {
        Detach();
    }
    void WhiterunMouseRoute::Attach(CefRefPtr<CefBrowser> browser, CefRefPtr<CefRenderHandler> render)
    {
        std::lock_guard lock(m_mutex);
        m_browser = browser;
        m_render = render;
    }
    bool WhiterunMouseRoute::Active() const
    {
        return m_window && m_browser && m_render && (!GetCapture() || GetCapture() == m_window) &&
            RouteActive(m_mode, m_focused, m_visible, GetForegroundWindow() == m_window, s_owner.load() == this);
    }
    unsigned WhiterunMouseRoute::Modifiers() const
    {
        unsigned result = 0;
        if (GetKeyState(VK_SHIFT) & 0x8000) result |= EVENTFLAG_SHIFT_DOWN;
        if (GetKeyState(VK_CONTROL) & 0x8000) result |= EVENTFLAG_CONTROL_DOWN;
        if (GetKeyState(VK_MENU) & 0x8000) result |= EVENTFLAG_ALT_DOWN;
        if (m_buttons.held & 1) result |= EVENTFLAG_LEFT_MOUSE_BUTTON;
        if (m_buttons.held & 2) result |= EVENTFLAG_RIGHT_MOUSE_BUTTON;
        if (m_buttons.held & 4) result |= EVENTFLAG_MIDDLE_MOUSE_BUTTON;
        return result;
    }
    void WhiterunMouseRoute::ReleaseAll()
    {
        const auto previous = m_buttons.ReleaseAll();
        if (m_browser && previous)
        {
            m_browser->GetHost()->SendCaptureLostEvent();
            CefMouseEvent event{};
            event.x = m_last.x; event.y = m_last.y; event.modifiers = Modifiers();
            for (const auto bit : {1, 2, 4})
            {
                if (!(previous & bit)) continue;
                const auto type = bit == 1 ? MBT_LEFT : bit == 2 ? MBT_RIGHT : MBT_MIDDLE;
                m_browser->GetHost()->SendMouseClickEvent(event, type, true, 1);
                ++m_syntheticReleases;
            }
        }
    }
    void WhiterunMouseRoute::Detach()
    {
        std::lock_guard lock(m_mutex);
        // OnBeforeClose forbids further browser calls. Clear references and state
        // without synthesizing CEF events, including from queued hook callbacks.
        m_focused = false;
        m_buttons.ReleaseAll();
        m_browser = nullptr;
        m_render = nullptr;
        m_hasPoint = false;
        auto expected = this;
        s_owner.compare_exchange_strong(expected, nullptr);
    }
    void WhiterunMouseRoute::PollDrag()
    {
        if (!Active() || !m_buttons.held) return;
        Snapshot();
        // Never steal or release Skyrim's HWND capture. Outside-client motion is
        // sampled while a held gesture is active; missing releases are reconciled.
        if (m_cursorValid)
        {
            const auto mapped = MapPoint(m_cursorX, m_cursorY, m_clientWidth, m_clientHeight,
                                         m_viewWidth, m_viewHeight, true);
            if (mapped && (mapped->x != m_last.x || mapped->y != m_last.y) &&
                (m_cursorX < 0 || m_cursorY < 0 || m_cursorX >= m_clientWidth || m_cursorY >= m_clientHeight))
            {
                m_last = *mapped;
                CefMouseEvent event{};
                event.x = m_last.x; event.y = m_last.y; event.modifiers = Modifiers();
                m_browser->GetHost()->SendMouseMoveEvent(event, false);
                ++m_forwarded;
            }
        }
        const std::uint8_t physical = ((GetAsyncKeyState(VK_LBUTTON) & 0x8000) ? 1 : 0) |
            ((GetAsyncKeyState(VK_RBUTTON) & 0x8000) ? 2 : 0) |
            ((GetAsyncKeyState(VK_MBUTTON) & 0x8000) ? 4 : 0);
        const auto released = MissingReleases(m_buttons.held, LogicalButtons(physical, GetSystemMetrics(SM_SWAPBUTTON) != 0));
        for (const auto bit : {1, 2, 4})
        {
            if (!(released & bit) || !m_buttons.Up(bit)) continue;
            CefMouseEvent event{};
            event.x = m_last.x; event.y = m_last.y; event.modifiers = Modifiers();
            const int index = bit == 1 ? 0 : bit == 2 ? 1 : 2;
            m_browser->GetHost()->SendMouseClickEvent(event,
                bit == 1 ? MBT_LEFT : bit == 2 ? MBT_RIGHT : MBT_MIDDLE, true, m_clickCounts[index]);
            ++m_syntheticReleases;
        }
    }
    void WhiterunMouseRoute::SetFocused(bool focused)
    {
        std::lock_guard lock(m_mutex);
        m_focused = focused;
        if (focused && m_visible && m_mode == Mode::Win32Mouse && m_browser) s_owner.store(this);
        else
        {
            ReleaseAll();
            auto expected = this;
            s_owner.compare_exchange_strong(expected, nullptr);
        }
    }
    void WhiterunMouseRoute::SetVisible(bool visible)
    {
        std::lock_guard lock(m_mutex);
        if (m_visible == visible) return;
        m_visible = visible;
        if (visible && m_focused && m_mode == Mode::Win32Mouse && m_browser) s_owner.store(this);
        else if (!visible)
        {
            ReleaseAll();
            auto expected = this;
            s_owner.compare_exchange_strong(expected, nullptr);
        }
    }
    void WhiterunMouseRoute::Snapshot()
    {
        if (!m_window) return;
        RECT rect{};
        if (GetClientRect(m_window, &rect))
        {
            m_clientWidth = rect.right - rect.left; m_clientHeight = rect.bottom - rect.top;
        }
        else m_clientWidth = m_clientHeight = 0;
        POINT cursor{};
        m_cursorValid = GetCursorPos(&cursor) && ScreenToClient(m_window, &cursor);
        if (m_cursorValid) { m_cursorX = cursor.x; m_cursorY = cursor.y; }
        if (m_render && m_browser)
        {
            CefRect view{};
            m_render->GetViewRect(m_browser, view);
            m_viewWidth = view.width; m_viewHeight = view.height;
        }
        using GetDpi = UINT(WINAPI*)(HWND);
        static auto getDpi = reinterpret_cast<GetDpi>(GetProcAddress(GetModuleHandleW(L"user32.dll"), "GetDpiForWindow"));
        m_dpi = getDpi ? getDpi(m_window) : 0;
    }
    void WhiterunMouseRoute::Trace()
    {
        if (m_mode == Mode::Native || !m_focused || !m_visible || !m_logger || m_logRows >= 600) return;
        const auto now = GetTickCount64();
        if (m_lastLog && now - m_lastLog < 1000) return;
        m_lastLog = now; ++m_logRows;
        Snapshot();
        // Deliberately no keyboard codes, text, URLs, window titles or process details.
        nlohmann::json row = {{"tick_ms", now}, {"row", m_logRows}, {"mode", m_mode == Mode::Diagnostics ? "diagnostics" : "win32-mouse"},
            {"foreground", m_window && GetForegroundWindow() == m_window}, {"owner", s_owner.load() == this},
            {"win_mouse_messages", m_winMessages}, {"win_key_messages", m_winKeyMessages}, {"native_moves", m_nativeMoves}, {"native_mouse_buttons", m_nativeButtons}, {"native_key_events", m_nativeKeys},
            {"forwarded", m_forwarded}, {"rejected", m_rejected}, {"synthetic_releases", m_syntheticReleases},
            {"held", m_buttons.held}, {"last_mouse_message", m_lastMessage}, {"client", {m_clientWidth, m_clientHeight}},
            {"view", {m_viewWidth, m_viewHeight}}, {"message_xy", {m_messageX, m_messageY}},
            {"win_cursor_valid", m_cursorValid}, {"win_cursor_xy", {m_cursorX, m_cursorY}},
            {"native_cursor_xy", {m_nativeX, m_nativeY}}, {"forwarded_xy", {m_last.x, m_last.y}}, {"window_dpi", m_dpi}};
        m_logger->info("WSINPUT {}", row.dump());
    }
    void WhiterunMouseRoute::RecordNativeMove(float x, float y)
    {
        std::lock_guard lock(m_mutex);
        if (!m_focused || !m_visible || m_mode == Mode::Native) return;
        ++m_nativeMoves; m_nativeX = x; m_nativeY = y;
    }
    void WhiterunMouseRoute::RecordNativeButton(bool mouse)
    {
        std::lock_guard lock(m_mutex);
        if (m_focused && m_visible && m_mode != Mode::Native)
        {
            if (mouse) ++m_nativeButtons;
            else ++m_nativeKeys;
        }
    }
    bool WhiterunMouseRoute::SuppressNativeMouse()
    {
        std::lock_guard lock(m_mutex);
        // Other still-focused browser wrappers must not receive duplicate native
        // mouse events while one Win32 route owns delivery.
        return m_window && m_browser && m_render &&
            RouteActive(m_mode, m_focused, m_visible, GetForegroundWindow() == m_window, s_owner.load() != nullptr);
    }
    std::optional<Point> WhiterunMouseRoute::Tick()
    {
        std::lock_guard lock(m_mutex);
        if ((!Active() || !m_visible) && m_buttons.held) ReleaseAll();
        PollDrag();
        Trace();
        return Active() && m_hasPoint ? std::optional<Point>(m_last) : std::nullopt;
    }
    void WhiterunMouseRoute::OnWindowMessage(HWND window, UINT message, WPARAM wparam, LPARAM lparam, bool& handled)
    {
        if (m_mode == Mode::Native) return;
        std::lock_guard lock(m_mutex);
        m_window = window;
        if ((message == WM_KEYDOWN || message == WM_KEYUP || message == WM_SYSKEYDOWN || message == WM_SYSKEYUP ||
             message == WM_CHAR || message == WM_SYSCHAR) && m_focused && m_visible) ++m_winKeyMessages;
        if (message == WM_KILLFOCUS || message == WM_CANCELMODE || message == WM_CAPTURECHANGED ||
            (message == WM_ACTIVATE && LOWORD(wparam) == WA_INACTIVE))
        {
            ReleaseAll();
            return;
        }
        const bool move = message == WM_MOUSEMOVE;
        const bool wheel = message == WM_MOUSEWHEEL || message == WM_MOUSEHWHEEL;
        const bool doubleClick = message == WM_LBUTTONDBLCLK || message == WM_RBUTTONDBLCLK || message == WM_MBUTTONDBLCLK;
        const bool down = doubleClick || message == WM_LBUTTONDOWN || message == WM_RBUTTONDOWN || message == WM_MBUTTONDOWN;
        const bool up = message == WM_LBUTTONUP || message == WM_RBUTTONUP || message == WM_MBUTTONUP;
        if (!move && !wheel && !down && !up) return;
        if (!m_focused || !m_visible) return;
        ++m_winMessages; m_lastMessage = message;
        POINT point{static_cast<short>(LOWORD(lparam)), static_cast<short>(HIWORD(lparam))};
        if (wheel && !ScreenToClient(window, &point)) { ++m_rejected; return; }
        m_messageX = point.x; m_messageY = point.y;
        if (handled || !Active()) return;
        if (GetCapture() && GetCapture() != window) { ++m_rejected; return; }
        Snapshot();
        const auto mapped = MapPoint(point.x, point.y, m_clientWidth, m_clientHeight, m_viewWidth, m_viewHeight, m_buttons.held != 0);
        if (!mapped) { ++m_rejected; return; }
        m_last = *mapped; m_hasPoint = true;
        const std::uint8_t bit = message == WM_LBUTTONDOWN || message == WM_LBUTTONUP || message == WM_LBUTTONDBLCLK ? 1 :
            message == WM_RBUTTONDOWN || message == WM_RBUTTONUP || message == WM_RBUTTONDBLCLK ? 2 : 4;
        if (down && !m_buttons.Down(bit)) { handled = true; return; }
        if (up && !m_buttons.Up(bit)) { handled = true; return; }
        const int buttonIndex = bit == 1 ? 0 : bit == 2 ? 1 : 2;
        if (down) m_clickCounts[buttonIndex] = doubleClick ? 2 : 1;
        CefMouseEvent event{};
        event.x = mapped->x; event.y = mapped->y; event.modifiers = Modifiers();
        const auto host = m_browser->GetHost();
        if (move) host->SendMouseMoveEvent(event, false);
        else if (wheel)
        {
            const int delta = static_cast<short>(HIWORD(wparam));
            host->SendMouseWheelEvent(event, message == WM_MOUSEHWHEEL ? delta : 0, message == WM_MOUSEWHEEL ? delta : 0);
        }
        else host->SendMouseClickEvent(event, bit == 1 ? MBT_LEFT : bit == 2 ? MBT_RIGHT : MBT_MIDDLE, up, m_clickCounts[buttonIndex]);
        ++m_forwarded; handled = true;
    }
}
