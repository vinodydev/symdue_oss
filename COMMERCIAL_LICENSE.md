# Symdue Commercial License

Symdue is dual-licensed. Most use cases are covered by the AGPL v3 + Apache 2.0 SDK split (see [LICENSE](LICENSE)). For specific use cases that need to escape the AGPL obligations on the runtime, we offer commercial licenses.

This document describes when you need a commercial license, when you don't, and what it costs.

## When you need a commercial license

You need a commercial license if you are:

1. **Embedding the Symdue runtime code directly in a closed-source commercial product** — for example, bundling Symdue as a library/dependency that ships inside your product binary, without releasing your product's source code under AGPL.

2. **Operating Symdue as a hyperscaler-class managed service** that offers Symdue as a hosted product to third-party customers — for example, "Cloud X Managed Symdue" or "Y Cloud's Workflow AI" service.

3. **Shipping proprietary modifications to the AGPL'd runtime** in a way that's network-accessible to third parties — for example, an agency hosting a fork of Symdue with custom-built features for paying clients, where you don't want to release the modifications under AGPL.

## When you do NOT need a commercial license

You do NOT need a commercial license for:

- **Self-hosting Symdue internally** for your own team or company. Internal use is unrestricted under AGPL.
- **Hosting unmodified Symdue for paying clients.** Display a "Source: github.com/vinodydev/symdue_oss" notice in your deployed UI; that's the entire AGPL obligation.
- **Building custom NodeTypes against the Apache 2.0 plugin SDK.** Your NodeType is a separate work; license it however you want, including proprietary.
- **Authoring workflows on Symdue.** Workflows are user content, not derivative works of the runtime.
- **Calling Symdue from your application via API** (HTTP, gRPC). Your application is a separate work; AGPL doesn't infect application code that calls AGPL software via clean API boundaries.
- **Modifying Symdue for internal use only**, with no network access to third parties. AGPL only applies when modified versions are network-accessible.

If your use case isn't listed in either column above, [contact us](#contact) — we'll give you a clear answer.

## License tiers

| Tier | Annual fee | Use case |
|---|---|---|
| **Standard Commercial** | $5,000 / year | Agency: ship proprietary core modifications (not buildable as Apache SDK plugins) |
| **Embedded Commercial — Standard** | $15,000 / year | SaaS: embed Symdue in commercial product (up to $5M ARR product) |
| **Embedded Commercial — Pro** | $35,000 / year | SaaS: embed Symdue in commercial product (up to $25M ARR product) |
| **Embedded Commercial — Enterprise** | $75,000 / year | SaaS: embed Symdue in commercial product (>$25M ARR or multiple products) |
| **Hyperscaler Commercial** | Contact for terms | Managed-service competitor offerings — typical structure: $100,000–500,000+/year base + revenue share |

## What you receive with a commercial license

- A non-AGPL commercial license that removes AGPL obligations for the licensed use case
- Right to embed, modify, or redistribute the Symdue runtime under the agreed terms
- Optional add-ons (priced separately): priority support, named technical contact, SLA terms, dedicated account engineer

## What we will and will not do with commercial licenses

**We will:**
- Quote fair terms based on your use case and scale
- Respond to inquiries within 2 business days
- Honor commercial license commitments for the contract duration regardless of any future OSS license changes
- Allow legitimate commercial competitors to license under standard terms (we will not block competitors via license refusal)

**We will not:**
- Use commercial licensing as a way to block competitors from operating
- Quote different terms based on whether a customer is "competing" with our Cloud
- Refuse to license to qualified prospects without specific cause (e.g., known bad-faith actors)
- Add hidden carve-outs in commercial license terms that aren't transparent at signing

This is consistent with our public commitment in [PRICING_PHILOSOPHY.md](PRICING_PHILOSOPHY.md): commercial licensing is for fair value capture, not market exclusion.

## Sales process

1. **Email us** describing your use case, target scale, and timeline. (See [Contact](#contact) below.)
2. **30-minute scoping call** to understand technical requirements and commercial constraints.
3. **Custom quote** delivered within 5-10 business days, typically.
4. **Master Service Agreement (MSA)** — we'll send a standard MSA template; you redline if needed; final negotiation typically 2-4 weeks.
5. **Sign annual contract**; license takes effect immediately upon signing.
6. **Renewable annually** at the same terms unless you upgrade (more product scale) or downgrade (less scale).

## License flexibility

If your use case changes during the contract period (e.g., your embedded product crosses an ARR threshold), we'll re-tier mid-contract on a fair basis (typically pro-rated to the next contract anniversary, no early-termination penalty).

If you outgrow Symdue and want to switch to a different workflow runtime, the commercial license terminates cleanly at end of annual term. No clawback. No mandatory continuation.

## Frequently asked questions

### Can we negotiate custom terms?

Yes. The pricing tiers above are starting points, not floors. Specific use cases may justify different terms — we'll be transparent about the math.

### What if our product fails / we shut down before contract end?

Annual contracts are paid annually in advance, but if your business pivots away from using Symdue commercially, we'll work with you on a partial refund or pro-rated termination. We're not in the business of extracting fees from dead products.

### Can we sublicense to our customers?

Generally no — the commercial license is for your specific commercial use case. If your customers want to embed Symdue independently, they need their own commercial license. We can structure broader sublicensing rights for partner/reseller arrangements at custom pricing.

### What about M&A scenarios?

Standard commercial licenses transfer with the company in an acquisition. If you're acquired by a hyperscaler-class company, the license tier may need to upgrade based on the acquirer's scale; we'll work with you on a transition.

### Can we trial a commercial license before committing?

Yes. We can structure a 30-day trial commercial license at $1,000 against the eventual annual fee. Use it to validate the integration, then convert to full annual contract.

## Contact

For commercial license inquiries:

**Email**: [vinody.dev@gmail.com](mailto:vinody.dev@gmail.com)

**Response time**: 2 business days

**What to include in your inquiry**:
- Brief description of your use case
- Approximate scale (employees, revenue, customer count, expected Symdue deployment size)
- Timeline (when do you need a license in place?)
- Any specific contract terms you'd want us to address upfront

We respond to every legitimate inquiry. We respect your time — we won't drag out sales cycles or upsell unnecessary tiers.

---

Symdue is licensed under AGPL v3 + Apache 2.0 SDK with commercial licenses for specific use cases. See [LICENSE](LICENSE) for the full license structure and [PRICING_PHILOSOPHY.md](PRICING_PHILOSOPHY.md) for our public commitments.
