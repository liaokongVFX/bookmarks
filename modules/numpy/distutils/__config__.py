# This file is generated by D:\BUILD\numpy-1.13.1\setup.py
# It contains system_info results at the time of building this package.
__all__ = ["get_info","show"]

lapack_mkl_info={'libraries': ['mkl_rt'], 'library_dirs': ['C:\\Program Files (x86)\\IntelSWTools\\parallel_studio_xe_2017.4.051\\compilers_and_libraries_2017\\windows\\mkl\\lib\\intel64'], 'define_macros': [('SCIPY_MKL_H', None), ('HAVE_CBLAS', None)], 'include_dirs': ['C:\\Program Files (x86)\\IntelSWTools\\parallel_studio_xe_2017.4.051\\compilers_and_libraries_2017\\windows\\mkl\\include']}
blas_mkl_info={'libraries': ['mkl_rt'], 'library_dirs': ['C:\\Program Files (x86)\\IntelSWTools\\parallel_studio_xe_2017.4.051\\compilers_and_libraries_2017\\windows\\mkl\\lib\\intel64'], 'define_macros': [('SCIPY_MKL_H', None), ('HAVE_CBLAS', None)], 'include_dirs': ['C:\\Program Files (x86)\\IntelSWTools\\parallel_studio_xe_2017.4.051\\compilers_and_libraries_2017\\windows\\mkl\\include']}
lapack_opt_info={'libraries': ['mkl_rt'], 'library_dirs': ['C:\\Program Files (x86)\\IntelSWTools\\parallel_studio_xe_2017.4.051\\compilers_and_libraries_2017\\windows\\mkl\\lib\\intel64'], 'define_macros': [('SCIPY_MKL_H', None), ('HAVE_CBLAS', None)], 'include_dirs': ['C:\\Program Files (x86)\\IntelSWTools\\parallel_studio_xe_2017.4.051\\compilers_and_libraries_2017\\windows\\mkl\\include']}
blas_opt_info={'libraries': ['mkl_rt'], 'library_dirs': ['C:\\Program Files (x86)\\IntelSWTools\\parallel_studio_xe_2017.4.051\\compilers_and_libraries_2017\\windows\\mkl\\lib\\intel64'], 'define_macros': [('SCIPY_MKL_H', None), ('HAVE_CBLAS', None)], 'include_dirs': ['C:\\Program Files (x86)\\IntelSWTools\\parallel_studio_xe_2017.4.051\\compilers_and_libraries_2017\\windows\\mkl\\include']}

def get_info(name):
    g = globals()
    return g.get(name, g.get(name + "_info", {}))

def show():
    for name,info_dict in globals().items():
        if name[0] == "_" or type(info_dict) is not type({}): continue
        print(name + ":")
        if not info_dict:
            print("  NOT AVAILABLE")
        for k,v in info_dict.items():
            v = str(v)
            if k == "sources" and len(v) > 200:
                v = v[:60] + " ...\n... " + v[-60:]
            print("    %s = %s" % (k,v))
    