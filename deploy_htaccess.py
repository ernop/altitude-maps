"""
Deploy .htaccess file to production server.
This enables gzip compression for JSON files.
"""
import subprocess
import sys
from pathlib import Path

def deploy_htaccess(remote_host: str, remote_path: str, remote_user: str):
    """
    Deploy .htaccess to production server via rsync.
    
    Args:
        remote_host: Server hostname (e.g., 'fuseki.net')
        remote_path: Remote directory path (e.g., '/home/username/fuseki.net/altitude-maps')
        remote_user: SSH username
    """
    htaccess_file = Path('.htaccess')
    
    if not htaccess_file.exists():
        print('[ERROR] .htaccess file not found!')
        return 1
    
    print('Deploying .htaccess to production server')
    print('=' * 70)
    print(f'File: {htaccess_file}')
    print(f'Destination: {remote_user}@{remote_host}:{remote_path}/')
    print()
    
    # Show what will be deployed
    print('[.htaccess contents]')
    print('-' * 70)
    with open(htaccess_file, 'r') as f:
        print(f.read())
    print('-' * 70)
    print()
    
    # Confirm
    response = input('Deploy this .htaccess file? (yes/no): ').strip().lower()
    if response not in ('yes', 'y'):
        print('Deployment cancelled.')
        return 0
    
    # Deploy via rsync
    remote_target = f"{remote_user}@{remote_host}:{remote_path}/"
    
    cmd = [
        'rsync',
        '-avz',
        '--progress',
        str(htaccess_file),
        remote_target
    ]
    
    print(f'\n[RSYNC] {" ".join(cmd)}')
    print()
    
    try:
        result = subprocess.run(cmd, check=True)
        
        print()
        print('=' * 70)
        print('[SUCCESS] .htaccess deployed!')
        print()
        print('NEXT STEPS:')
        print('1. Test compression with: python test_nebraska_compression.py')
        print('2. Expected: Should now show "Content-Encoding: gzip"')
        print('3. File size should drop from ~8 MB to ~0.5-1 MB')
        print()
        print('If compression still not working:')
        print('  - Check Dreamhost panel: ensure mod_deflate is enabled')
        print('  - Try .htaccess syntax checker')
        print('  - Contact Dreamhost support')
        
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f'\n[ERROR] rsync failed: {e}')
        print('\nTroubleshooting:')
        print('  - Ensure you have SSH access to the server')
        print('  - Check the remote path is correct')
        print('  - You may need to manually upload .htaccess via FTP/SFTP')
        return 1
    except FileNotFoundError:
        print('[ERROR] rsync not found!')
        print('\nAlternatives:')
        print('  1. Install rsync: winget install rsync')
        print('  2. Manually upload .htaccess via FTP/SFTP')
        print('  3. Use Dreamhost file manager to upload')
        return 1

def main():
    """Main entry point."""
    print('Deploy .htaccess to enable gzip compression')
    print()
    
    # Get server details
    remote_host = input('Server hostname [fuseki.net]: ').strip() or 'fuseki.net'
    remote_user = input('SSH username: ').strip()
    remote_path = input('Remote path [~/fuseki.net/altitude-maps]: ').strip() or '~/fuseki.net/altitude-maps'
    
    if not remote_user:
        print('[ERROR] SSH username required')
        return 1
    
    print()
    return deploy_htaccess(remote_host, remote_path, remote_user)

if __name__ == '__main__':
    sys.exit(main())

