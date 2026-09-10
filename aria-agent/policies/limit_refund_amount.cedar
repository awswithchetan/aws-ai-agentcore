// ShopSmart Policy: Allow refund requests only up to $500.
// Refunds over $500 match no permit and are denied by Cedar's default-deny —
// enforced at the Gateway boundary, so it cannot be bypassed by prompt injection.
// The `has` check and comparison must share the same `&&` for Cedar to safely
// access the optional attribute.
permit(
  principal,
  action == AgentCore::Action::"ShopSmartAPI___submit_request",
  resource == AgentCore::Gateway::"<GATEWAY_ARN>"
)
when {
  context.input has refund_amount && context.input.refund_amount <= 500
};
