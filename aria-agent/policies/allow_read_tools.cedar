// ShopSmart Policy: Allow all read-only tool calls
// These operations carry no risk of data modification and are always permitted.
// Note: retrieve_from_knowledge_base is a local agent tool (not via Gateway),
// so it is not — and cannot be — policy-controlled here.
permit(
  principal,
  action in [
    AgentCore::Action::"ShopSmartAPI___get_order",
    AgentCore::Action::"ShopSmartAPI___list_orders",
    AgentCore::Action::"ShopSmartAPI___get_product",
    AgentCore::Action::"ShopSmartAPI___search_products"
  ],
  resource == AgentCore::Gateway::"<GATEWAY_ARN>"
);
