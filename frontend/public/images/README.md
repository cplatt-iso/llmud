# Graphics Assets

This directory contains all visual assets for the MUD frontend.

## Directory Structure:

- **ui/** - UI elements (buttons, borders, frames, panels)
- **icons/** - Small icons (room types, skills, status effects)
- **portraits/** - Character portraits, NPC faces
- **items/** - Item graphics (weapons, armor, consumables, etc.)
- **mobs/** - Monster and creature graphics
- **backgrounds/** - Room backgrounds, terrain textures
- **effects/** - Combat effects, spell animations, particle effects

## Usage in React:

```jsx
// Static reference
<img src="/images/items/sword_001.png" alt="Iron Sword" />

// Dynamic reference
const iconPath = `/images/icons/${iconName}.png`;
<img src={iconPath} alt={description} />
```

## Naming Conventions:

- Use lowercase with underscores: `iron_sword_001.png`
- Include variation numbers: `goblin_001.png`, `goblin_002.png`
- Be descriptive: `health_potion_small.png` vs `hp_pot_sm.png`