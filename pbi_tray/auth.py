"""
MSAL Authentication for Power BI Tray application.

Handles Azure AD authentication with persistent token caching.
"""

import threading
from pathlib import Path

import msal

from .config import (
    CLIENT_ID,
    AUTHORITY, 
    SCOPES,
    TOKEN_CACHE_FILE,
    state,
)
from .utils.logging import log


# Thread-safe MSAL operations
_msal_app = None
_token_cache = None
_msal_lock = threading.Lock()


def init_token_cache() -> None:
    """Initialize persistent token cache."""
    global _token_cache
    
    # Only initialize once - don't recreate if already exists
    if _token_cache is not None:
        return
    
    _token_cache = msal.SerializableTokenCache()
    
    # Load existing cache if available
    if TOKEN_CACHE_FILE.exists():
        try:
            with open(TOKEN_CACHE_FILE, "r") as f:
                cache_data = f.read()
                if cache_data and cache_data != "{}":
                    _token_cache.deserialize(cache_data)
                    log(f"Token cache loaded from {TOKEN_CACHE_FILE}")
                else:
                    log("Token cache file is empty")
        except Exception as e:
            log(f"Warning: Could not load token cache: {e}")
    else:
        log("No existing token cache file")


def save_token_cache(force: bool = False) -> None:
    """Save token cache to file."""
    if _token_cache is None:
        return
    
    # Save if state changed OR if forced (e.g., after interactive login)
    if force or _token_cache.has_state_changed:
        try:
            cache_data = _token_cache.serialize()
            if cache_data and cache_data != "{}":
                with open(TOKEN_CACHE_FILE, "w") as f:
                    f.write(cache_data)
                log("Token cache saved successfully")
        except Exception as e:
            log(f"Warning: Could not save token cache: {e}")


def get_msal_app() -> msal.PublicClientApplication:
    """Get or create MSAL public client application (thread-safe)."""
    global _msal_app
    
    with _msal_lock:
        if _msal_app is None:
            log(f"Creating new MSAL app (token_cache is {'set' if _token_cache else 'None'})")
            init_token_cache()
            _msal_app = msal.PublicClientApplication(
                CLIENT_ID,
                authority=AUTHORITY,
                token_cache=_token_cache
            )
        
        return _msal_app


def is_authenticated() -> bool:
    """Check if user has valid cached credentials (without prompting)."""
    try:
        app = get_msal_app()
        accounts = app.get_accounts()
        return len(accounts) > 0
    except Exception as e:
        print(f"is_authenticated error: {e}")
        return False


def get_access_token_silent() -> str | None:
    """
    Try to get access token silently (no user interaction).
    Returns token if available, None if login required.
    """
    app = get_msal_app()
    accounts = app.get_accounts()
    
    if not accounts:
        # No cached accounts - user needs to sign in
        state.auth_error_message = "Not signed in"
        return None
    
    # Try to get token silently (from cache or refresh)
    result = app.acquire_token_silent(SCOPES, account=accounts[0])
    
    if result and "access_token" in result:
        save_token_cache()
        state.auth_error_message = None
        return result["access_token"]
    
    # Silent acquisition failed - token might be expired and refresh failed
    state.auth_error_message = "Session expired - please sign in again"
    return None


def get_access_token_interactive() -> str | None:
    """
    Get access token with interactive login (opens browser).
    """
    app = get_msal_app()
    
    print("\n" + "=" * 60)
    print("Authentication required - opening browser...")
    print("=" * 60 + "\n")
    
    try:
        result = app.acquire_token_interactive(
            SCOPES,
            prompt="select_account"
        )
        
        if result and "access_token" in result:
            # Force save after interactive login to ensure cache is persisted
            save_token_cache(force=True)
            state.auth_error_message = None
            log("Authentication successful! Token cached for future use.")
            return result["access_token"]
        else:
            error = result.get("error_description", result.get("error", "Unknown error"))
            state.auth_error_message = f"Auth failed: {error}"
            log(f"Authentication failed: {error}")
            return None
            
    except Exception as e:
        state.auth_error_message = f"Auth error: {str(e)}"
        log(f"Authentication error: {e}")
        return None


def get_account_name() -> str | None:
    """Get the signed-in account name."""
    try:
        app = get_msal_app()
        accounts = app.get_accounts()
        if accounts:
            return accounts[0].get("username", "Unknown")
    except Exception:
        pass
    return None


def sign_out() -> None:
    """Sign out and clear cached tokens."""
    global _msal_app, _token_cache
    
    with _msal_lock:
        # Clear the token cache file
        if TOKEN_CACHE_FILE.exists():
            try:
                TOKEN_CACHE_FILE.unlink()
                log("Token cache cleared.")
            except Exception as e:
                log(f"Error clearing token cache: {e}")
        
        # Reset MSAL app to force re-authentication
        _msal_app = None
        _token_cache = None
    
    # Clear cached names
    state.semantic_model_name = None
    state.workspace_name = None
    
    log("Signed out. You will need to authenticate on next refresh.")


def sign_in() -> str | None:
    """Force interactive sign-in (resets any cached state first)."""
    global _msal_app, _token_cache
    
    # Use lock to safely reset globals
    with _msal_lock:
        _msal_app = None
        _token_cache = None
        if TOKEN_CACHE_FILE.exists():
            TOKEN_CACHE_FILE.unlink()
    
    # Trigger interactive authentication
    token = get_access_token_interactive()
    if token:
        log("Sign-in successful!")
    else:
        log("Sign-in was cancelled or failed.")
    return token
