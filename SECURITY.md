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

Runtime controls enforce authority; model instructions only describe it. Fail closed when identity, capability, policy, or validation cannot establish permission. Do not let an agent change the controls that grant its current authority without separate approval.

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

An agent receives only the authority its task explicitly grants. Anything else is denied. Information can request an action, but it cannot authorize one. Agents cannot delegate authority they do not possess.

Assume any single agent, tool, or integration can be compromised. Keep its credentials and reachable resources narrow so one compromise does not grant broad access. Separate destructive and production authority from ordinary workers where practical. Keep recovery credentials outside ordinary agent reach.

Treat third-party and API responses as untrusted input before they can trigger privileged behavior. Give integrations only the credentials and operations they need.

## When to threat-model

Create or expand a threat model when the project gains meaningful external input, authentication/authorization, sensitive data, privileged tools, destructive actions, third-party execution, deployment authority, or autonomous agents. The `security-hardening` add-on provides a stronger template when needed.

## Reporting a vulnerability

For a public repository, configure a private security reporting channel and replace this section with the project-specific process before the first public release.

Do not open a public issue for an unpatched vulnerability that exposes users or infrastructure.

## Automated checks

The base security workflow checks repository hygiene and dependency changes. Add stack-specific scanning behind project hooks as the implementation stack becomes known. Security automation supplements review; it does not replace trust-boundary design.
