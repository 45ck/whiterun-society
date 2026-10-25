#include "../InputPolicy.h"
#include <iostream>
#include <limits>

int main()
{
    using namespace NL::Input;
    unsigned checks = 0, failures = 0;
    const auto require = [&](bool value, const char* label) { ++checks; if (!value) { ++failures; std::cerr << label << '\n'; } };
    require(ParseMode("") == Mode::Native && ParseMode("typo") == Mode::Native, "default is native");
    require(ParseMode("diagnostics") == Mode::Diagnostics, "diagnostic mode");
    require(ParseMode("win32-mouse") == Mode::Win32Mouse, "explicit mouse mode");
    auto p = MapPoint(960, 540, 1920, 1080, 1280, 720, false);
    require(p && p->x == 640 && p->y == 360, "client-to-render scale applied once");
    p = MapPoint(0, 0, 1920, 1080, 1280, 720, false);
    require(p && p->x == 0 && p->y == 0, "top left");
    p = MapPoint(1919, 1079, 1920, 1080, 1280, 720, false);
    require(p && p->x == 1279 && p->y == 719, "bottom right");
    require(!MapPoint(-1, 30, 1920, 1080, 1280, 720, false), "outside click rejected");
    require(!MapPoint(1920, 30, 1920, 1080, 1280, 720, false), "exclusive right bound");
    p = MapPoint(-50, 2000, 1920, 1080, 1280, 720, true);
    require(p && p->x == 0 && p->y == 719, "outside gesture release is clamped");
    require(!MapPoint(1, 1, 0, 1080, 1280, 720, false), "zero client dimensions");
    require(!MapPoint(1, 1, 1920, 1080, -1, 720, false), "invalid render dimensions");
    require(!MapPoint(std::numeric_limits<double>::quiet_NaN(), 1, 1920, 1080, 1280, 720, true), "nan rejected");
    require(!MapPoint(1, std::numeric_limits<double>::infinity(), 1920, 1080, 1280, 720, true), "infinity rejected");
    for (int flags = 0; flags < 16; ++flags)
    {
        const bool focused = flags & 1, visible = flags & 2, foreground = flags & 4, owner = flags & 8;
        require(RouteActive(Mode::Win32Mouse, focused, visible, foreground, owner) == (flags == 15), "all route gates required");
        require(!RouteActive(Mode::Native, focused, visible, foreground, owner), "native never redirects");
        require(!RouteActive(Mode::Diagnostics, focused, visible, foreground, owner), "diagnostics never redirects");
    }
    Buttons buttons;
    require(!buttons.Up(1), "orphan up not forwarded");
    require(buttons.Down(1) && !buttons.Down(1), "duplicate down suppressed");
    require(buttons.Down(4) && buttons.held == 5, "independent simultaneous buttons");
    require(!buttons.Down(3) && !buttons.Up(3), "invalid button mask rejected");
    require(buttons.ReleaseAll() == 5 && buttons.ReleaseAll() == 0, "focus loss releases once");
    require(buttons.Down(2) && buttons.Up(2) && !buttons.Up(2), "new focus can start clean gesture");
    for (int held = 0; held < 8; ++held)
        for (int physical = 0; physical < 8; ++physical)
            require(MissingReleases(held, physical) == (held & (7 ^ physical)), "only tracked missing releases");
    for (int physical = 0; physical < 8; ++physical)
    {
        require(LogicalButtons(physical, false) == physical, "unswapped mapping");
        const auto swapped = LogicalButtons(physical, true);
        require((swapped & 1) == ((physical & 2) >> 1) && (swapped & 2) == ((physical & 1) << 1) &&
                (swapped & 4) == (physical & 4), "swapped physical buttons map to logical messages");
    }
    buttons.Down(1); buttons.Down(4);
    const auto missing = MissingReleases(buttons.held, 4);
    require(missing == 1 && buttons.Up(missing), "one button released while another held");
    require(MissingReleases(buttons.held, 4) == 0, "polled release is emitted once");
    require(RouteActive(Mode::Win32Mouse, true, true, true, true), "any owner suppresses old focused route native path");
    // A request before load caches the desired state; ready callback must apply it once.
    bool current = false, cached = false, ready = false;
    unsigned actualFocusApplications = 0;
    const auto request = [&](bool requested) {
        if (!ShouldApplyFocus(current, requested, cached)) return;
        if (!ready) { current = requested; cached = true; return; }
        current = requested; cached = false; ++actualFocusApplications;
    };
    request(true);
    require(current && cached && actualFocusApplications == 0, "preload request defers");
    ready = true; request(true);
    require(current && !cached && actualFocusApplications == 1, "ready callback applies cached focus");
    request(true);
    require(actualFocusApplications == 1, "settled identical focus is idempotent");
    request(false);
    require(!current && actualFocusApplications == 2, "focus release applied");
    // A replacement browser must reapply desired focus only once its page loads.
    request(true);
    const auto beforeReattach = actualFocusApplications;
    ready = false; cached = CacheFocusOnAttach(current, cached);
    require(cached && actualFocusApplications == beforeReattach, "focused reattach remains deferred");
    ready = true; request(current);
    require(current && !cached && actualFocusApplications == beforeReattach + 1, "reattach load restores actual focus once");
    request(current);
    require(actualFocusApplications == beforeReattach + 1, "reattach settled focus remains idempotent");
    request(false);
    ready = false; cached = CacheFocusOnAttach(current, cached);
    require(!cached && !current, "unfocused reattach remains unfocused");
    require(CacheFocusOnAttach(false, true), "explicit cached unfocus survives attach");
    std::cout << checks << " checks; " << failures << " failures\n";
    return failures ? 1 : 0;
}
