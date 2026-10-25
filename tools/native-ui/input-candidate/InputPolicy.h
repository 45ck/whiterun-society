#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <optional>
#include <string_view>

namespace NL::Input
{
    enum class Mode { Native, Diagnostics, Win32Mouse };
    inline Mode ParseMode(std::string_view value)
    {
        if (value == "diagnostics") return Mode::Diagnostics;
        if (value == "win32-mouse") return Mode::Win32Mouse;
        return Mode::Native;
    }
    struct Point { int x; int y; };
    inline std::optional<Point> MapPoint(double x, double y, int clientWidth, int clientHeight,
                                        int viewWidth, int viewHeight, bool dragging)
    {
        if (!std::isfinite(x) || !std::isfinite(y) || clientWidth <= 0 || clientHeight <= 0 ||
            viewWidth <= 0 || viewHeight <= 0 || clientWidth > 32768 || clientHeight > 32768 ||
            viewWidth > 32768 || viewHeight > 32768) return std::nullopt;
        if (!dragging && (x < 0 || y < 0 || x >= clientWidth || y >= clientHeight)) return std::nullopt;
        return Point{static_cast<int>(std::floor(std::clamp(x * viewWidth / clientWidth, 0.0, double(viewWidth - 1)))),
                     static_cast<int>(std::floor(std::clamp(y * viewHeight / clientHeight, 0.0, double(viewHeight - 1))))};
    }
    inline bool RouteActive(Mode mode, bool focused, bool visible, bool foreground, bool owner)
    {
        return mode == Mode::Win32Mouse && focused && visible && foreground && owner;
    }
    inline bool ShouldApplyFocus(bool current, bool requested, bool cached)
    {
        return current != requested || cached;
    }
    inline bool CacheFocusOnAttach(bool requested, bool cached)
    {
        return requested || cached;
    }
    inline std::uint8_t LogicalButtons(std::uint8_t physical, bool swapped)
    {
        return swapped ? ((physical & 1) << 1) | ((physical & 2) >> 1) | (physical & 4) : physical & 7;
    }
    inline std::uint8_t MissingReleases(std::uint8_t held, std::uint8_t physical)
    {
        return held & ~physical & 7;
    }
    struct Buttons
    {
        std::uint8_t held = 0;
        bool Down(std::uint8_t bit)
        {
            if (bit != 1 && bit != 2 && bit != 4) return false;
            if (held & bit) return false;
            held |= bit;
            return true;
        }
        bool Up(std::uint8_t bit)
        {
            if (bit != 1 && bit != 2 && bit != 4) return false;
            if (!(held & bit)) return false;
            held &= ~bit;
            return true;
        }
        std::uint8_t ReleaseAll()
        {
            const auto previous = held;
            held = 0;
            return previous;
        }
    };
}
