# Apple Glass Morphism UI - Visual Design Guide

## Overview
Your CS2BanChecker GUI has been transformed with a modern **Apple glass morphism** design language. This design brings a premium, contemporary look that's visually appealing and user-friendly.

## Design Characteristics

### 1. Dark Mode Foundation
- **Deep background**: `#0A0E27` (nearly black with slight blue tint)
- Creates reduced eye strain and modern aesthetic
- Pairs well with bright accent colors

### 2. Glass Morphism Effect
The UI implements the glass morphism technique through:
- **Semi-transparent surfaces**: Layered glass-like cards
- **Rounded corners**: 20px radius for soft, modern appearance  
- **Subtle borders**: Barely visible outlines for definition
- **Frosted glass appearance**: Soft, blurred-edge look

### 3. Color Palette

#### Core Colors
| Element | Color | Hex Value | Purpose |
|---------|-------|-----------|---------|
| Background | Deep Blue | `#0A0E27` | Main canvas |
| Surface | Light Blue | `#1A1F3A` | Card backgrounds |
| Surface Alt | Medium Blue | `#252D4D` | Hover states |
| Text Primary | Off-white | `#F5F5F7` | Main text |
| Text Muted | Gray | `#A1A1A6` | Secondary text |

#### Action Colors (Apple System)
| State | Color | Hex Value |
|-------|-------|-----------|
| Accent/Primary | System Blue | `#0A84FF` |
| Success | System Green | `#34C759` |
| Warning | System Orange | `#FF9500` |
| Danger | System Red | `#FF3B30` |

### 4. Typography
- **Font**: SF Pro Display (Apple's system font)
  - Fallback: System fonts will be used if not available
- **Sizes**:
  - Body text: 10pt
  - Regular labels: 11pt
  - Bold labels: 11pt bold
  - Titles: 13pt bold
  - Monospace (logs): Monaco 10pt

### 5. Components

#### Glass Cards
- Semi-transparent background with subtle border
- Rounded corners (20px)
- Padding: 16px internal spacing
- Used for all major sections

#### Buttons
**Primary (Blue)**
- Background: Apple System Blue (`#0A84FF`)
- State: Active `#0973EA`, Disabled `#1A1F3A`
- Hover: Slightly darker blue

**Danger (Red)**
- Background: Apple System Red (`#FF3B30`)
- State: Active `#E63228`, Disabled `#1A1F3A`

**Warning (Orange)**
- Background: Apple System Orange (`#FF9500`)
- State: Active `#E68600`, Disabled `#1A1F3A`

**Secondary (Glass)**
- Background: Semi-transparent surface (`#1A1F3A`)
- Hover: Darker surface (`#252D4D`)

#### Tabs
- Inactive: Muted text on dark background
- Active: Accent blue text with underline

#### Treeview (Table)
- Row height: 28px for easy reading
- Selected row: Light blue background (`#252D4D`)
- Columns maintain proper alignment

### 6. Interactive Elements

#### Hover States
- Buttons: Slight background color shift
- Cards: Subtle glow (improved visibility)
- Text: Color changes for status updates

#### Disabled States
- Reduced opacity appearance
- Muted text color
- Clear visual distinction from enabled state

#### Focus States
- Color accent highlighting
- Smooth transitions
- No harsh outlines

## Visual Hierarchy

1. **Primary Action**: Blue buttons (Start Bot)
2. **Secondary Action**: Glass surface buttons (Update Prices)
3. **Destructive Action**: Red buttons (Stop Bot)
4. **Informational**: Muted text on glass cards
5. **Status**: Color-coded labels (Green = Running, Red = Stopped, Orange = Paused)

## Spacing Standards

| Element | Value | Usage |
|---------|-------|-------|
| Card Padding | 16px | Internal card spacing |
| Section Gap | 12px | Between cards |
| Button Gap | 6px | Between buttons |
| Element Margin | 8px | Between elements |

## Accessibility Features

? **High Contrast**: Off-white text on dark backgrounds
? **Color Coding**: Multiple colors used with symbols (? ? ?)
? **Large Click Areas**: Buttons are 28px minimum height
? **Clear Status**: Visual indicators with proper hierarchy
? **Professional Fonts**: SF Pro Display for readability

## Benefits of This Design

1. **Modern Aesthetic**: Keeps your application current with 2024 UI trends
2. **Apple Consistency**: Uses Apple's actual system colors and design language
3. **Reduced Eye Strain**: Dark mode suitable for extended use
4. **Professional Appearance**: Looks polished and intentional
5. **Better Usability**: Clear visual hierarchy guides user actions
6. **Cross-Platform**: Works perfectly on Windows, macOS, and Linux

## CSS-Like Styling Reference

```
Primary Button:
  Background: #0A84FF
  Text: White
  Padding: 14px 16px
  Border-radius: 8px
  Font-weight: bold

Glass Card:
  Background: #1A1F3A (semi-transparent)
  Border: 1px #252D4D
  Border-radius: 20px
  Padding: 16px
  Box-shadow: subtle inner glow

Status Running:
  Color: #34C759 (Green)

Status Paused:
  Color: #FF9500 (Orange)

Status Stopped:
  Color: #FF3B30 (Red)
```

## macOS-Specific Features

On macOS systems, the application will:
- Use the transparent/unified window style if available
- Properly integrate with the system appearance
- Respect system color scheme preferences

## Future Customization

To modify colors, simply edit the constants at the top of `utils/gui.py`:
- `BG_PRIMARY` - Main background
- `ACCENT` - Accent color
- `SUCCESS`, `WARNING`, `DANGER` - Status colors

All components automatically use these values, so theme-wide changes are easy!
