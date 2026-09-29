# ADR 0002: One repo per product, created from a template

- **Date:** 2026-09-29
- **Status:** accepted

## Context
Many products, each with different domain logic, deploys and data. Core improvements should be reusable.

## Decision
The Factory is a GitHub template repo (kept private). Each product is a separate repo created from it, with the Factory added as a `factory` git remote so core updates can be merged in. Product changes stay in `product/`, `domain/`, `features/` and `integrations/`; fixed core lives in `core/` and `design-system/`, which keeps merges from the Factory conflict-free. A `/new-product` Claude skill will automate setup once the core is built.

## Alternatives considered
- GitHub fork: keeps an upstream link but public-repo forks must stay public, risky for healthcare/pharmacy products.
- One monorepo for all products: a bad change or deploy could affect every product.

## Consequences
Each product deploys and fails independently. Core updates are pulled in per product on purpose.
