// ShopSmart Policy: Block refund requests exceeding $500
// Refunds over $500 require manual review — Aria cannot approve them automatically.
// This rule cannot be bypassed through prompt injection because it is enforced
// at the Gateway boundary, outside of agent code.
forbid(
  principal,
  action == AgentCore::Action::"ShopSmartAPI___submit_request",
  resource == AgentCore::Gateway::"<GATEWAY_ARN>"
)
when {
  context.input has refund_amount &&
  context.input.refund_amount > 500
};
