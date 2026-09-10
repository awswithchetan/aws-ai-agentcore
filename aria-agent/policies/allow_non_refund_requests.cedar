// ShopSmart Policy: Allow support requests that carry no refund amount
// (complaints, inquiries, exchanges without a refund) so the refund cap in
// limit_refund_amount.cedar does not accidentally block them.
permit(
  principal,
  action == AgentCore::Action::"ShopSmartAPI___submit_request",
  resource == AgentCore::Gateway::"<GATEWAY_ARN>"
)
when {
  !(context.input has refund_amount)
};
