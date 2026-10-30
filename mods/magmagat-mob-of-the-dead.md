# Magmagat for Mob of the Dead (Plutonium T6)

A port of Black Ops 4's Magmagat to Black Ops II's Mob of the Dead on Plutonium, with the forge quest from copforthat's Black Ops III remaster of the map. It installs as a single mod from the in-game Mods menu.

Source: <https://github.com/lborruto/t6_motd_magmagat>

![The Magmagat on Mob of the Dead](https://github.com/user-attachments/assets/4a9d67df-2768-44cf-ada5-aeab68fc9fd9)

## What it adds

- **The quest.** Place a Blundergat in the Warden's Office fireplace and survive a lockdown collecting 15 souls. Then carry the tempered gun to the forge by the docks before its 15-second temper burns out, using five blue drums on the way to refill it.
- **The weapon.** A lobbed lava blob that sticks to what it hits: zombies blow apart or burn, and a missed shot leaves a lava pool that pulls zombies into its fire. Pack-a-Punched, it becomes the Magmus Operandi.
- **Black Ops 4's rules.** Damage, timings, the lure, burning, the burst, Brutus, points and Insta-Kill were checked line by line against Black Ops 4's decompiled weapon script ([`zm_weap_blundergat.gsc`](https://github.com/shiversoftdev/t8-src/blob/main/scripts/zm/weapons/zm_weap_blundergat.gsc)). Fire rate, reload, ammo and sounds were read from the game itself.

## How it's built

- **GSC scripts** for the quest, the weapon and the forge, split by system (`mg_quest`, `mg_forge`, `mg_weapon`…).
- **Assets ported from Black Ops 4 and III** (models, textures, effects, sounds) and packed with OpenAssetTools into a Black Ops II fastfile.
- **A Perl toolchain** (`tools/`) for the whole pipeline: DDS/PNG conversion, recolouring, sound import, building the weapon and the mod, linting includes and sounds, packing the release.

## How to install

1. Download `zm_magmagat-<version>.zip` from the [latest release](https://github.com/lborruto/t6_motd_magmagat/releases/latest).
2. Unzip it into `%localappdata%\Plutonium\storage\t6\`, so you get `...\t6\mods\zm_magmagat\`.
3. In game: **Mods** → **Magmagat**, then play **Mob of the Dead**. The console prints `[MG] Magmagat <version> loaded`.

The step-by-step quest is in the repo's [walkthrough](https://github.com/lborruto/t6_motd_magmagat/blob/main/docs/GUIDE.md).

A free, non-commercial fan project. The game assets belong to Activision / Treyarch, and the quest's effects are used with copforthat's permission. See the [credits](https://github.com/lborruto/t6_motd_magmagat#credits).
