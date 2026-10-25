#pragma once
#include "PCH.h"
#include "Hooks/InputPolicy.h"
#include <atomic>
#include <array>
#include <mutex>

namespace NL::Input
{
    // Owns CEF references, never a DefaultBrowser pointer. Hook callbacks retain a
    // shared_ptr so an in-flight callback cannot access a destroyed browser wrapper.
    class WhiterunMouseRoute
    {
        inline static std::atomic<WhiterunMouseRoute*> s_owner{nullptr};
        mutable std::recursive_mutex m_mutex;
        Mode m_mode = Mode::Native;
        bool m_focused = false, m_visible = true;
        HWND m_window = nullptr;
        CefRefPtr<CefBrowser> m_browser;
        CefRefPtr<CefRenderHandler> m_render;
        std::shared_ptr<spdlog::logger> m_logger;
        Buttons m_buttons;
        Point m_last{0, 0};
        bool m_hasPoint = false;
        std::array<int, 3> m_clickCounts{1, 1, 1};
        std::uint64_t m_winMessages = 0, m_winKeyMessages = 0, m_nativeMoves = 0, m_nativeButtons = 0, m_nativeKeys = 0;
        std::uint64_t m_forwarded = 0, m_rejected = 0, m_syntheticReleases = 0;
        std::uint64_t m_lastLog = 0, m_logRows = 0;
        float m_nativeX = 0, m_nativeY = 0;
        unsigned m_lastMessage = 0;
        int m_clientWidth = 0, m_clientHeight = 0, m_viewWidth = 0, m_viewHeight = 0;
        int m_messageX = 0, m_messageY = 0, m_cursorX = 0, m_cursorY = 0;
        bool m_cursorValid = false;
        unsigned m_dpi = 0;

        bool Active() const;
        unsigned Modifiers() const;
        void ReleaseAll();
        void PollDrag();
        void Snapshot();
        void Trace();

    public:
        explicit WhiterunMouseRoute(std::shared_ptr<spdlog::logger> logger);
        ~WhiterunMouseRoute();
        void Attach(CefRefPtr<CefBrowser> browser, CefRefPtr<CefRenderHandler> render);
        void Detach();
        void SetFocused(bool focused);
        void SetVisible(bool visible);
        void OnWindowMessage(HWND window, UINT message, WPARAM wparam, LPARAM lparam, bool& handled);
        void RecordNativeMove(float x, float y);
        void RecordNativeButton(bool mouse);
        bool SuppressNativeMouse();
        std::optional<Point> Tick();
    };
}
