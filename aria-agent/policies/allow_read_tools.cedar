// ShopSmart Policy: Allow all read-only tool calls
// These operations carry no risk of data modification and are always permitted.
permit(
  principal,
  action in [
    AgentCore::Action::"ShopSmartAPI___get_order",
    AgentCore::Action::"ShopSmartAPI___list_orders",
    AgentCore::Action::"ShopSmartAPI___get_product",
    AgentCore::Action::"ShopSmartAPI___search_products",
    AgentCore::Action::"ShopSmartAPI___get_knowledge_base_answer"
  ],
  resource == AgentCore::Gateway::"<GATEWAY_ARN>"
);
