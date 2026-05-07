# Symdue Pricing Philosophy

This document is a **public commitment**. We are stating, on the record, what Symdue will and will not do — so that anyone evaluating Symdue can trust the boundary between what's free and what's paid, today and in the future.

The runtime is built around three commitments that we will never change.

## 1. The runtime is AGPL v3 forever

We commit to keeping the Symdue runtime under the GNU Affero General Public License v3.0 or later. We will **not** relicense to a more restrictive license — not BSL, not SSPL, not the Elastic License v2, not the Sustainable Use License, not "fair source," not "ethical source," not any custom license we invent.

If we ever break this commitment, you can fork the AGPL'd code from the last AGPL release and continue independently. AGPL guarantees this right.

## 2. The plugin SDK + spec is Apache 2.0 forever

The NodeType plugin SDK, workflow JSON schemas, and public API specifications stay under Apache License 2.0 forever. We will **not** move SDK or spec code into the AGPL'd runtime. We will **not** restrict plugin authors' freedom to license their NodeType code however they wish.

This means: custom NodeTypes you write against the Apache 2.0 SDK are your IP. License them as proprietary, MIT, AGPL, or any other terms — your choice.

## 3. No ads, no upsell prompts, no telemetry by default

Symdue OSS will never contain:

- Advertisements (banner ads, sponsored content, promoted templates in the canvas)
- In-app upsell prompts ("upgrade to unlock this feature")
- Telemetry collection enabled by default

We collect data only with your explicit opt-in or via your Cloud subscription. We will never add these patterns to the OSS distribution.

If we ever add telemetry to Symdue OSS, it will be:
- Off by default
- Opt-in via a clear command or settings toggle
- Transparently documented (every field collected listed in public docs)
- One-command disable, persistent across upgrades
- Separate opt-ins for "product analytics" and "crash reporting"

## How dual-licensing works (the power dynamic, in plain English)

AGPL is a permission grant **from us (the copyright owner) to you**. We are not bound by AGPL on our own code. This is by design and is exactly the model MongoDB Atlas, Grafana Cloud, Sentry SaaS, and GitLab.com all rely on.

What this means in practice:

- **Symdue Cloud is unrestricted for us.** We can host the AGPL runtime, add proprietary Cloud-only features (collaborative editing, eval dashboards, FinOps, OEM SDK), serve managed deployments to paying customers, and never release Cloud source. AGPL applies to *other people* who use our AGPL'd code, not to us.
- **You (someone else) are bound by AGPL** when you modify the runtime and serve it network-accessible to third parties.
- **The CLA preserves this dynamic.** External contributors grant us broad relicensing rights so we can continue to offer commercial licenses and host Cloud as the codebase grows.

This is not a hidden trick — it's the entire reason dual-licensing exists. The license costs our *competitors* (hyperscalers, third-party SaaS embedders, deep-modification commercial copies) revenue extraction options that don't exist under Apache 2.0. It costs *us* essentially nothing because we own the code.

We commit to using this asymmetry **only for fair commercial protection**, not for market exclusion. We will not refuse commercial licenses to legitimate competitors; we'll quote fair terms based on use case. The license is about ensuring fair value capture, not blocking competition.

## What we DO charge for

These are the tiers where Symdue generates revenue:

- **Cloud / BYOC managed deployment** — we operate Symdue for you on our infrastructure or your cloud account, with SLA. Pricing: $1,500–10,000/month depending on tier.
- **Enterprise tier features** — SSO, fine-grained RBAC, audit log retention, multi-region HA, OEM SDK access, compliance certification packages (SOC 2 / HIPAA / GDPR), eval dashboards, FinOps tracking, dedicated account engineer. Pricing: custom annual contracts, $50,000–250,000+/year.
- **Commercial licenses** — for specific use cases that need to escape AGPL obligations (embedding Symdue in a closed-source product, hyperscaler-class managed service operation, proprietary runtime modifications). See [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md).
- **Support contracts** — SLA-backed support tiers (Bronze / Silver / Gold). Pricing: $5,000–35,000/year.
- **Verified Partner Program** (year 2+) — third-party integration certification + marketplace badge. Pricing: $5,000/year per partner.
- **Premium templates and kits** (year 2+) — verified, support-backed kits in the marketplace. Marketplace transaction fees: 15–25%.
- **Training and certification** (year 3+) — official courses and "Symdue Certified Engineer" credential.

## What we will never do

These are commitments — not preferences. We're stating them publicly so you can hold us accountable.

- Add ads to the OSS app
- Add upsell prompts to the OSS app
- Add telemetry-by-default to the OSS app
- Relicense the OSS code to a more restrictive license (BSL, SSPL, Elastic License, SUL, custom licenses)
- Move features that are currently OSS into a paid-only tier
- Refuse commercial licenses to legitimate competitors as a way to block them
- Use the "owner not bound" property to ship hidden non-AGPL features into the OSS distribution and call it AGPL
- Sell user data, pass it to advertisers, or share it with third parties without explicit opt-in

If we ever break any of these, you can fork the codebase and call it out publicly. The AGPL license guarantees the right to fork; the public commitment in this document is what gives you the standing to call us out.

## Why this document exists

Open source companies have a history of changing the rules under their users:

- HashiCorp moved Apache 2.0 → BSL in 2023 (community fork: OpenTofu)
- Elastic moved Apache 2.0 → SSPL → Elastic License v2 → "Free + Open" (community fork: OpenSearch)
- Redis moved BSD → RSAL/SSPL (community fork: Valkey)
- MongoDB moved AGPL → SSPL
- Sentry moved BSD → BSL (community pushback was loud)

We're choosing to make explicit, public commitments about what we will and will not do — at the moment of OSS launch — so that anyone considering Symdue for production deployment can plan with confidence.

This document trades flexibility for trust. The trust is what compounds adoption.

If we ever need to change these commitments, we will:
1. Announce the change at least 90 days in advance
2. Explain the specific commercial pressure that justifies the change
3. Provide a clear migration path for users who want to fork the AGPL release
4. Accept that breaking the commitment costs us reputation we won't recover

We don't expect to ever need to break these commitments. The dual-license + commercial license structure is designed specifically to give us commercial sustainability without requiring further license tightening.

---

Symdue is licensed under AGPL v3 with an Apache 2.0 plugin SDK + spec, dual-licensed for specific commercial use cases. Maintained by Vinod Y and contributors. See [LICENSE](LICENSE) for the full structure.
