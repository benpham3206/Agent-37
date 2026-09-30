# Security policy

## Baseline

- Never commit secrets, credentials, private keys, production tokens, or populated `.env` files.
- Treat external input, model output, and tool output as untrusted at privileged boundaries.
- Keep permissions narrower than the possible action space of the code or model using them.
- Validate sensitive filesystem paths, URLs, commands, tool arguments, and structured actions before execution.
- Prefer allowlists and least privilege where practical.
- Keep production credentials out of examples, fixtures, and ordinary developer workflows.

## Agent and tool authority

A model may propose an action; policy determines whether it is allowed.

Enforce authority at runtime; model instructions describe it. Fail closed when identity, capability, policy, or validation cannot establish permission. Agents need separate approval to change controls granting their current authority.

```text
intent
  ↓
identity
  ↓
capability
  ↓
policy
  ↓
validation
  ↓
execution
  ↓
audit
```

More capable models do not automatically receive broader secrets, filesystem, network, deployment, or production permissions.

Deny authority the task does not explicitly grant. Information can request actions, not authorize them. Agents cannot delegate authority they lack.

Assume any agent, tool, or integration can be compromised. Limit its credentials and reachable resources. Separate destructive and production authority from ordinary workers where practical; keep recovery credentials outside their reach.

Treat third-party/API responses as untrusted before privileged behavior. Give integrations only required credentials and operations.

## When to threat-model

Create or expand a threat model for meaningful external input, authentication/authorization, sensitive data, privileged tools, destructive actions, third-party execution, deployment authority, or autonomous agents. Use the `security-hardening` add-on’s stronger template when needed.

## Reporting a vulnerability

Before the first public release, configure private security reporting and replace this section with the project process.

Do not open a public issue for an unpatched vulnerability that exposes users or infrastructure.

## Automated checks

The base workflow checks repository hygiene and dependency changes. Add stack-specific scanning behind project hooks when the stack is known. Automation supplements review and trust-boundary design.
