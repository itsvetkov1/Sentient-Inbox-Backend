"""
Application Startup Script

Manages the application startup process with proper initialization, error handling,
and environment setup. Ensures all required components are available before
starting the main application.

This script implements comprehensive error handling following system specifications,
providing a robust startup process with proper logging and recovery mechanisms.

Usage:
    python start.py [mode]

Arguments:
    mode: 'api' to run the API server, 'process' to run email processing (default: both)

Returns:
    0 if startup successful, 1 otherwise
"""

import os
import sys
import subprocess
import logging
import argparse
import time
from pathlib import Path


def parse_arguments():
    """Parse command line arguments with proper validation."""
    parser = argparse.ArgumentParser(description="Start the Email Management Application")
    
    parser.add_argument(
        "mode", 
        nargs="?",
        choices=["api", "process", "both"],
        default="both",
        help="Startup mode: 'api' for API server, 'process' for email processing, 'both' for complete application"
    )
    
    parser.add_argument(
        "--host", 
        default="127.0.0.1",
        help="Host address for API server (default: 127.0.0.1)"
    )
    
    parser.add_argument(
        "--port", 
        type=int,
        default=8000,
        help="Port for API server (default: 8000)"
    )
    
    parser.add_argument(
        "--env",
        choices=["development", "testing", "production"],
        default="development",
        help="Environment to run in (default: development)"
    )
    
    parser.add_argument(
        "--skip-init",
        action="store_true",
        help="Skip initialization steps"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Email batch size for processing (default: 50)"
    )
    
    return parser.parse_args()


def setup_logging():
    """Configure comprehensive logging for startup process."""
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/startup.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("startup")


def run_initialization():
    """
    Run pre-startup initialization with proper error handling.
    
    Implements comprehensive initialization following system specifications
    and error handling protocols, ensuring proper application preparation.
    
    Returns:
        bool: True if initialization successful, False otherwise
    """
    logger = logging.getLogger("startup.init")
    logger.info("Running pre-startup initialization")
    
    try:
        # Check if pre_startup script exists
        pre_startup_path = Path("pre_startup.py")
        if not pre_startup_path.exists():
            logger.error(f"Pre-startup script not found: {pre_startup_path}")
            return False
        
        # Run the pre-startup script
        result = subprocess.run(
            [sys.executable, "pre_startup.py"],
            check=True,
            capture_output=True,
            text=True
        )
        
        # Log output from pre-startup
        for line in result.stdout.splitlines():
            logger.info(f"Init: {line}")
            
        logger.info("Pre-startup initialization completed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Pre-startup initialization failed: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Error running pre-startup initialization: {str(e)}")
        return False


def run_api_server(host, port, env):
    """
    Start the API server with proper error handling.
    
    Implements API server startup following system specifications,
    providing proper error handling and logging.
    
    Args:
        host: Host address to bind server
        port: Port to bind server
        env: Environment context
        
    Returns:
        subprocess.Popen: Running process or None if startup failed
    """
    logger = logging.getLogger("startup.api")
    logger.info(f"Starting API server on {host}:{port} in {env} environment")
    
    try:
        # Check if run_api.py script exists
        api_script = Path("run_api.py")
        if not api_script.exists():
            logger.error(f"API server script not found: {api_script}")
            return None
        
        # Build command
        cmd = [
            sys.executable,
            "run_api.py",
            "--host", host,
            "--port", str(port),
            "--env", env
        ]
        
        # Add reload flag in development mode
        if env == "development":
            cmd.append("--reload")
        
        # Start process without waiting
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Give it a moment to detect immediate startup errors
        time.sleep(2)
        
        if process.poll() is not None:
            # Process already exited
            stdout, stderr = process.communicate()
            logger.error(f"API server failed to start: {stderr}")
            return None
            
        logger.info("API server started successfully")
        return process
        
    except Exception as e:
        logger.error(f"Error starting API server: {str(e)}")
        return None


def run_email_processor(batch_size):
    """
    Start the email processor with proper error handling.
    
    Implements email processor startup following system specifications,
    providing proper error handling and logging.
    
    Args:
        batch_size: Number of emails to process in batch
        
    Returns:
        subprocess.Popen: Running process or None if startup failed
    """
    logger = logging.getLogger("startup.processor")
    logger.info(f"Starting email processor with batch size {batch_size}")
    
    try:
        # Check if main.py script exists
        processor_script = Path("main.py")
        if not processor_script.exists():
            logger.error(f"Email processor script not found: {processor_script}")
            return None
        
        # Start process
        process = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env={**os.environ, "BATCH_SIZE": str(batch_size)}
        )
        
        # Give it a moment to detect immediate startup errors
        time.sleep(2)
        
        if process.poll() is not None:
            # Process already exited
            stdout, stderr = process.communicate()
            logger.error(f"Email processor failed to start: {stderr}")
            return None
            
        logger.info("Email processor started successfully")
        return process
        
    except Exception as e:
        logger.error(f"Error starting email processor: {str(e)}")
        return None


def monitor_processes(processes):
    """
    Monitor running processes and log their output.
    
    Implements comprehensive process monitoring with proper output
    capturing and error handling following system specifications.
    
    Args:
        processes: Dictionary of running processes {name: process}
    """
    logger = logging.getLogger("startup.monitor")
    logger.info(f"Monitoring {len(processes)} processes")
    
    # Setup process-specific loggers
    process_loggers = {}
    for name in processes:
        process_loggers[name] = logging.getLogger(f"process.{name}")
    
    try:
        while processes:
            for name, process in list(processes.items()):
                # Check if process is still running
                if process.poll() is not None:
                    # Process exited
                    stdout, stderr = process.communicate()
                    logger.warning(f"Process '{name}' exited with code {process.returncode}")
                    
                    if stderr:
                        logger.error(f"Process '{name}' error output: {stderr}")
                    
                    del processes[name]
                    continue
                
                # Read output (non-blocking)
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    process_loggers[name].info(line.rstrip())
            
            # Short sleep to prevent CPU overuse
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down processes")
        shutdown_processes(processes)
    except Exception as e:
        logger.error(f"Error monitoring processes: {str(e)}")
        shutdown_processes(processes)


def shutdown_processes(processes):
    """
    Safely shut down running processes.
    
    Implements graceful process termination following system specifications,
    ensuring proper cleanup on application shutdown.
    
    Args:
        processes: Dictionary of running processes {name: process}
    """
    logger = logging.getLogger("startup.shutdown")
    logger.info(f"Shutting down {len(processes)} processes")
    
    for name, process in processes.items():
        try:
            logger.info(f"Terminating process: {name}")
            process.terminate()
            
            # Give process time to terminate gracefully
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning(f"Process {name} did not terminate gracefully, killing")
            process.kill()
        except Exception as e:
            logger.error(f"Error shutting down process {name}: {str(e)}")


def main():
    """
    Main application startup sequence.
    
    Implements comprehensive application startup following system
    specifications and error handling protocols, providing a robust
    startup process with proper component initialization and monitoring.
    
    Returns:
        int: 0 for success, 1 for failure
    """
    # Parse arguments
    args = parse_arguments()
    
    # Setup logging
    logger = setup_logging()
    logger.info("=== Starting Email Management Application ===")
    logger.info(f"Starting in mode: {args.mode}, environment: {args.env}")
    
    # Run initialization unless explicitly skipped
    if not args.skip_init:
        init_success = run_initialization()
        if not init_success:
            logger.error("Initialization failed, aborting startup")
            return 1
    else:
        logger.info("Initialization skipped due to --skip-init flag")
    
    # Track running processes
    processes = {}
    
    # Start components based on selected mode
    if args.mode in ["api", "both"]:
        api_process = run_api_server(args.host, args.port, args.env)
        if api_process:
            processes["api"] = api_process
        else:
            logger.error("Failed to start API server")
            if args.mode == "api":
                return 1
    
    if args.mode in ["process", "both"]:
        processor_process = run_email_processor(args.batch_size)
        if processor_process:
            processes["processor"] = processor_process
        else:
            logger.error("Failed to start email processor")
            if args.mode == "process":
                # Shut down any started processes before exiting
                shutdown_processes(processes)
                return 1
    
    # Check if any processes started successfully
    if not processes:
        logger.error("No processes started successfully, aborting")
        return 1
    
    logger.info(f"Successfully started {len(processes)} components")
    
    # Monitor running processes
    try:
        monitor_processes(processes)
    except KeyboardInterrupt:
        logger.info("Application shutdown requested by user")
    finally:
        # Ensure all processes are terminated on exit
        shutdown_processes(processes)
    
    logger.info("=== Application shutdown complete ===")
    return 0