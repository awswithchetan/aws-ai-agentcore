// ShopSmart Policy: Allow return/refund requests within the $500 limit
// The forbid in block-large-refunds.cedar overrides this when amount > 500.
permit(
  principal,
  action == AgentCore::Action::"ShopSmartAPI___submit_request",
  resource == AgentCore::Gateway::"<GATEWAY_ARN>"
);
