#!/usr/bin/env python3
"""Example usage of LangChain tools."""
from app.tools import (
    get_all_tools, get_tool_by_name,
    find_account_tool, list_pricebooks_tool, list_skus_tool,
    create_quote_tool, get_quote_tool, render_quote_pdf_tool
)


def demonstrate_tools():
    """Demonstrate the available tools."""
    print("=== LangChain Tools for Sales Quoting Engine ===\n")
    
    # Get all available tools
    tools = get_all_tools()
    print(f"Total tools available: {len(tools)}\n")
    
    # Display tool information
    for tool in tools:
        print(f"Tool: {tool.name}")
        print(f"Description: {tool.description}")
        if hasattr(tool, 'args_schema') and tool.args_schema:
            print(f"Input Schema: {tool.args_schema.__name__}")
        print("-" * 50)
    
    print("\n=== Tool Usage Examples ===\n")
    
    # Example 1: Account Search
    print("1. Account Search Tool")
    print("   Purpose: Find accounts by name or domain")
    print("   Usage: find_account_tool('acme')")
    print("   Returns: List of matching accounts with confidence scores")
    print()
    
    # Example 2: Pricebook Listing
    print("2. Pricebook Listing Tool")
    print("   Purpose: List all available pricebooks")
    print("   Usage: list_pricebooks_tool()")
    print("   Returns: List of pricebooks with currencies and default status")
    print()
    
    # Example 3: SKU Listing
    print("3. SKU Listing Tool")
    print("   Purpose: List SKUs with optional filtering")
    print("   Usage: list_skus_tool({'name': 'laptop', 'pricebook_id': 1})")
    print("   Returns: List of matching SKUs with details")
    print()
    
    # Example 4: Quote Creation
    print("4. Quote Creation Tool")
    print("   Purpose: Create new quotes with validated line items")
    print("   Usage: create_quote_tool(account_id=1, pricebook_id=1, lines=[...])")
    print("   Returns: Created quote details with ID and status")
    print()
    
    # Example 5: Quote Retrieval
    print("5. Quote Retrieval Tool")
    print("   Purpose: Get complete quote details by ID")
    print("   Usage: get_quote_tool(quote_id=123)")
    print("   Returns: Complete quote with line items and totals")
    print()
    
    # Example 6: PDF Generation
    print("6. PDF Generation Tool")
    print("   Purpose: Generate PDF for a quote")
    print("   Usage: render_quote_pdf_tool(quote_id=123)")
    print("   Returns: PDF URL and generation status")
    print()


def demonstrate_tool_registry():
    """Demonstrate tool registry functionality."""
    print("=== Tool Registry Functions ===\n")
    
    # Get tool by name
    find_account_tool = get_tool_by_name("find_account")
    if find_account_tool:
        print(f"Found tool: {find_account_tool.name}")
        print(f"Description: {find_account_tool.description}")
    
    # Get non-existing tool
    non_existing = get_tool_by_name("non_existing")
    print(f"Non-existing tool: {non_existing}")
    
    print()


def demonstrate_validation():
    """Demonstrate input validation."""
    print("=== Input Validation Examples ===\n")
    
    print("Quote Line Validation:")
    print("- Quantity must be >= 1")
    print("- Discount percentage must be between 0.0 and 1.0")
    print("- SKU ID must be a positive integer")
    print("- Unit price must be non-negative (if provided)")
    print()
    
    print("Quote Creation Validation:")
    print("- Account ID must be positive")
    print("- Pricebook ID must be positive")
    print("- Must have at least one line item")
    print("- All line items must have valid SKU ID and quantity")
    print()


def demonstrate_integration():
    """Demonstrate how tools integrate with LangChain."""
    print("=== LangChain Integration ===\n")
    
    print("These tools are designed to work with:")
    print("- LangChain agents for automated quote creation")
    print("- Structured input/output for reliable AI interactions")
    print("- Proper error handling and validation")
    print("- Database session management")
    print()
    
    print("Agent Workflow Example:")
    print("1. User asks to create a quote for 'Acme Corp'")
    print("2. Agent uses find_account_tool to locate the account")
    print("3. Agent uses list_pricebooks_tool to get available pricebooks")
    print("4. Agent uses list_skus_tool to find relevant products")
    print("5. Agent uses create_quote_tool to create the quote")
    print("6. Agent uses render_quote_pdf_tool to generate PDF")
    print("7. Agent returns quote details and PDF URL to user")


def main():
    """Main function to run examples."""
    demonstrate_tools()
    demonstrate_tool_registry()
    demonstrate_validation()
    demonstrate_integration()
    
    print("=== Implementation Notes ===\n")
    print("Note: These tools require a database session to function.")
    print("In a real LangChain agent, the session would be injected")
    print("by the agent framework or dependency injection system.")
    print()
    print("The tools are designed to be stateless and can be")
    print("easily integrated into any LangChain workflow.")


if __name__ == "__main__":
    main()
