# Quick Reference - Apple Glass Morphism UI

## What Changed

Your CS2BanChecker GUI now features:
- **Apple glass morphism** design aesthetic
- **Dark mode** with off-white text
- **Semi-transparent cards** with frosted glass effect
- **Modern color palette** using Apple system colors
- **Smooth transitions** and hover effects
- **Better visual hierarchy** with improved typography
- **Professional appearance** matching modern apps

## Color Palette (Quick Copy)

```python
# Core Colors
BG_PRIMARY = "#0A0E27"          # Deep background
BG_SURFACE = "#1A1F3A"          # Glass surface
BG_SURFACE_ALT = "#252D4D"      # Hover surface
FG_PRIMARY = "#F5F5F7"          # Main text
FG_MUTED = "#A1A1A6"            # Secondary text

# Action Colors (Apple System)
ACCENT = "#0A84FF"              # Primary button / blue
SUCCESS = "#34C759"             # Status running / green
WARNING = "#FF9500"             # Status paused / orange
DANGER = "#FF3B30"              # Status stopped / red
```

## UI Components

| Component | Visual | Style |
|-----------|--------|-------|
| **Main Background** | Almost black | Deep blue `#0A0E27` |
| **Cards** | Frosted glass | Semi-transparent blue `#1A1F3A` |
| **Buttons** | Colored rectangles | Rounded, bold text |
| **Tabs** | Underlined text | Active = blue, Inactive = gray |
| **Trees/Tables** | Dark rows | Light blue selection `#252D4D` |
| **Text** | Off-white | Primary `#F5F5F7`, Muted `#A1A1A6` |

## Button Types

```
Primary:    Blue (#0A84FF)      ? "? Start Bot"
Danger:     Red (#FF3B30)       ? "? Stop Bot"
Warning:    Orange (#FF9500)    ? "? Pause"
Secondary:  Glass surface       ? "? Resume", "?? Restart"
```

## Typography

- **Font Family**: SF Pro Display (Apple's system font)
- **Body Text**: 10pt
- **Labels**: 11pt
- **Bold**: 11pt bold or 13pt bold for titles
- **Monospace**: Monaco 10pt (for logs)

## Status Colors

```
?? Running:  #34C759 (Green)
?? Paused:   #FF9500 (Orange)
?? Stopped:  #FF3B30 (Red)
```

## Spacing Standards

- **Card Padding**: 16px
- **Section Gap**: 12px
- **Button Gap**: 6px
- **Element Margin**: 8px
- **Card Radius**: 20px

## File Modified

- `utils/gui.py` - Complete redesign with apple glass morphism theme

## Key Features Added

? `GlassCard` class for frosted glass effect
? Apple system color palette
? SF Pro Display typography
? Modern button styling
? Smooth hover states
? Better visual hierarchy
? Dark mode throughout
? macOS transparency support

## How to Use

1. Simply run your application normally
2. The GUI will automatically load with the new apple glass morphism theme
3. All functionality remains the same - only appearance changed
4. Works on Windows, macOS, and Linux

## To Customize Colors

Edit constants at the top of `utils/gui.py`:

```python
BG_PRIMARY = "#0A0E27"      # Change main background
ACCENT = "#0A84FF"          # Change primary blue
SUCCESS = "#34C759"         # Change success green
WARNING = "#FF9500"         # Change warning orange
DANGER = "#FF3B30"          # Change danger red
```

All components automatically use these values!

## Browser Equivalent

If you're familiar with web design, this is like:
```css
/* Main container */
background: linear-gradient(to bottom, #0A0E27, #0A1533);

/* Glass card effect */
.card {
  background: rgba(26, 31, 58, 0.7);
  backdrop-filter: blur(10px);
  border-radius: 20px;
  border: 1px solid rgba(37, 45, 77, 0.5);
}

/* Button hover */
button:hover {
  background: rgba(37, 45, 77, 0.9);
  transition: all 200ms ease;
}
```

## Platform Support

| OS | Status | Notes |
|------|--------|-------|
| Windows | ? Excellent | Full glass morphism support |
| macOS | ? Excellent | Native transparency integration |
| Linux | ? Good | Clean modern appearance |

## Backward Compatibility

? All existing functionality preserved
? No new dependencies required  
? Same tkinter library used
? All callbacks work as before
? Python 3.8+ compatible

## Performance

- No performance impact
- Native tkinter components only
- Efficient rendering
- Smooth animations
- Lightweight design

---

**Enjoy your new Apple glass morphism UI! ??**
