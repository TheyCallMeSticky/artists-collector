#!/usr/bin/env python3
"""
Script pour exécuter tous les tests du projet Artists Collector
"""

import os
import sys
import subprocess
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.append(str(Path(__file__).parent.parent))

def run_tests():
    """Exécuter tous les tests"""
    print("🧪 Exécution des tests Artists Collector")
    print("=" * 50)
    
    # Installer pytest si nécessaire
    try:
        import pytest
    except ImportError:
        print("📦 Installation de pytest...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pytest", "pytest-cov"], check=True)
    
    # Changer vers le répertoire du projet
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    # Commande pytest avec couverture
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--cov=app",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov"
    ]
    
    try:
        result = subprocess.run(cmd, check=False)
        
        if result.returncode == 0:
            print("\n✅ Tous les tests sont passés!")
            print("📊 Rapport de couverture généré dans htmlcov/")
        else:
            print(f"\n❌ Certains tests ont échoué (code de retour: {result.returncode})")
            
        return result.returncode
        
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution des tests: {e}")
        return 1

def run_linting():
    """Exécuter les vérifications de style de code"""
    print("\n🔍 Vérification du style de code")
    print("=" * 50)
    
    # Installer les outils de linting si nécessaire
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "flake8", "black", "isort"], 
                      check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("⚠️  Impossible d'installer les outils de linting")
        return 1
    
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    # Vérifier avec flake8
    print("🔍 Vérification avec flake8...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "flake8", 
            "app/", "tests/",
            "--max-line-length=100",
            "--ignore=E203,W503"
        ], check=False, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Aucun problème de style détecté")
        else:
            print("⚠️  Problèmes de style détectés:")
            print(result.stdout)
    except Exception as e:
        print(f"❌ Erreur lors de la vérification flake8: {e}")
    
    # Vérifier le formatage avec black
    print("\n🔍 Vérification du formatage avec black...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "black", 
            "--check", "--diff",
            "app/", "tests/"
        ], check=False, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Code correctement formaté")
        else:
            print("⚠️  Code nécessite un reformatage:")
            print(result.stdout)
    except Exception as e:
        print(f"❌ Erreur lors de la vérification black: {e}")
    
    # Vérifier les imports avec isort
    print("\n🔍 Vérification des imports avec isort...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "isort", 
            "--check-only", "--diff",
            "app/", "tests/"
        ], check=False, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Imports correctement organisés")
        else:
            print("⚠️  Imports nécessitent une réorganisation:")
            print(result.stdout)
    except Exception as e:
        print(f"❌ Erreur lors de la vérification isort: {e}")

def run_security_check():
    """Exécuter les vérifications de sécurité"""
    print("\n🔒 Vérification de sécurité")
    print("=" * 50)
    
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "bandit"], 
                      check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("⚠️  Impossible d'installer bandit")
        return
    
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "bandit", 
            "-r", "app/",
            "-f", "txt"
        ], check=False, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Aucun problème de sécurité détecté")
        else:
            print("⚠️  Problèmes de sécurité potentiels:")
            print(result.stdout)
    except Exception as e:
        print(f"❌ Erreur lors de la vérification de sécurité: {e}")

def main():
    """Fonction principale"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Exécuter les tests et vérifications")
    parser.add_argument("--tests-only", action="store_true", 
                       help="Exécuter seulement les tests")
    parser.add_argument("--lint-only", action="store_true", 
                       help="Exécuter seulement le linting")
    parser.add_argument("--security-only", action="store_true", 
                       help="Exécuter seulement les vérifications de sécurité")
    
    args = parser.parse_args()
    
    if args.tests_only:
        return run_tests()
    elif args.lint_only:
        run_linting()
        return 0
    elif args.security_only:
        run_security_check()
        return 0
    else:
        # Exécuter tout
        test_result = run_tests()
        run_linting()
        run_security_check()
        
        print("\n" + "=" * 50)
        if test_result == 0:
            print("🎉 Tous les tests sont passés!")
        else:
            print("❌ Certains tests ont échoué")
        
        return test_result

if __name__ == "__main__":
    sys.exit(main())
