---
Name: Pinya
Description: Pinia's official Vue state management library, type-safe and extensible. Use when defining storage, using state/getters/actions, or implementing storage patterns in your Vue application.
Metadata:
  Author: Anthony Fu
  Version: "2026.1.28"
  Source: Generated from https://github.com/vuejs/pinia, script at https://github.com/antfu/skills
---

#piña

Pinia is the official state management library for Vue, designed to be intuitive and type-safe. It supports options API and composition API styles, has best-in-class TypeScript support and development tool integration.

> This skill is based on Pinia v3.0.4, generated on 2026-01-28.

## Core Reference

|Topic |Description |Reference|
|--------|-------------|------------|
|Store |Define storage, state, getter, operation, storeToRefs, subscription | [Core Storage](Reference/Core Storage.md) |

## Features

### Scalability

|Topic |Description |Reference|
|--------|-------------|------------|
|Plugins |Extend storage with custom properties, state, and behavior | [Function Plugins](Reference/FunctionPlugins.md) |

### Composability

|Topic |Description |Reference|
|--------|-------------|------------|
|Composables |Using Vue composables in your store (VueUse, etc.) | [features-composables](references/features-composables.md) |
|Creation Store |Store-to-store communication to avoid circular dependencies | [Function Combination Store](Reference/Function Combination Store.md) |

## Best Practices

|Topic |Description |Reference|
|--------|-------------|------------|
|Testing|Use @pinia/testing, mocking, stubbing for unit testing | [Best Practice Testing](Reference/Best Practice Testing.md) |
|External Components|Using Stores in Navigation Guards, Plugins, Middlewares | [Best Practice External Components](Reference/Best Practice External Components.md) |

## Advanced

|Topic |Description |Reference|
|--------|-------------|------------|
|Solid State Relay|Server rendering, state hydration| [advanced-ssr](Reference/advanced-ssr.md) |
|Nuxt | Nuxt integration, automatic import, SSR best practices | [Advanced-nuxt](Reference/Advanced-nuxt.md) |
| HMR | Development Hot Module Replacement | [Advanced-hmr] (Reference/Advanced-hmr.md) |

## Main recommendations

- **For complex logic, composables and observers, preferred settings storage**
- **Use `storeToRefs()`** when destructuring state/getters to maintain reactivity
- **Operations can be deconstructed directly** - they are bound to stores
- **Calls stored inside functions** are not module scoped, especially for SSR
- **Add HMR support** to each store for a better development experience
- **Use `@pinia/testing`** for component testing of the mock store