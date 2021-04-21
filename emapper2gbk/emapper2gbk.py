# Copyright (C) 2019-2021 Clémence Frioux & Arnaud Belcour - Inria Dyliss - Pleiade
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>

import logging
import os
import csv
import sys

from emapper2gbk import genomes_to_gbk
from emapper2gbk import genes_to_gbk
from emapper2gbk.utils import create_GO_namespaces_alternatives, get_basename, is_valid_dir, is_valid_file, is_valid_path, get_extension, read_annotation
from multiprocessing import Pool

logger = logging.getLogger(__name__)

def gbk_creation(nucleic_fasta:str, protein_fasta:str, annot:str,
                org:str, output_path:str, gobasic:str, cpu:int=1,
                gff:str=None, merge_genes_fake_contig:int=None):
    """Create gbk files from list of genes or genomes and eggnog-mapper annotation outputs.

    Args:
        nucleic_fasta (str): nucleic fasta file or dir
        protein_fasta (str): protein fasta file or dir
        annot (str): annotation file or dir
        org (str): organims name or mapping file
        output_path (str): output file or directory
        gobasic (str): path to go-basic.obo file
        cpu (int, optional): number of cpu, used for multi process in directory mode. Defaults to 1.
        gff (str, optional): gff file or dir. Defaults to None.
        merge_genes_fake_contig (int, optional): merge genes into fake contig. The int associted to merge is the number of genes per fake contigs.
    """
    # Check if inputs are folders or files.
    types = {input_file: 'directory' if os.path.isdir(input_file)
                else
                'file' if os.path.isfile(input_file)
                else None
                    for input_file in [nucleic_fasta, protein_fasta, annot]}

    if gff:
        types[gff] = 'directory' if os.path.isdir(gff) else 'file' if os.path.isfile(gff) else None

    if all(input_file == 'file' for input_file in types.values()):
        directory_mode = False
        one_annot_file = True
    elif all(input_file == 'directory' for input_file in types.values()):
        directory_mode = True
        one_annot_file = False
    elif all(types[input_file] == 'directory' for input_file in types if input_file != annot) and types[annot] == 'file':
        directory_mode = True
        one_annot_file = True
    else:
        logger.critical(f"Invalid combinations of input, three are possible: all inputs (nucleic fasta, protein fasta, annotation, [gff]) are files, all inputs are directories or annotation is file and the other inputs are directories.")
        sys.exit(1)

    # Ensure output directory or output file can be written.
    if directory_mode and not is_valid_dir(output_path):
        logger.critical(f"Output dir path is incorrect (does not exist or cannot be written)")
        sys.exit(1)
    elif not directory_mode and not is_valid_path(output_path):
        logger.critical(f"Output file path cannot be accessed")
        sys.exit(1)

    if not directory_mode:
        if gff:
            genomes_to_gbk.main(nucleic_fasta=nucleic_fasta, protein_fasta=protein_fasta, annot=annot,
                                    gff=gff, org=org, output_path=output_path, gobasic=gobasic)
        else:
            genes_to_gbk.main(nucleic_fasta=nucleic_fasta, protein_fasta=protein_fasta, annot=annot,
                                org=org, output_path=output_path, gobasic=gobasic,
                                merge_genes_fake_contig=merge_genes_fake_contig)
    else:
        gbk_pool = Pool(processes=cpu)

        all_genomes = set([get_basename(i) for i in os.listdir(nucleic_fasta)])

        # filename or single org name
        if is_valid_file(org):
            with open(org, 'r') as csvfile:
                try:
                    dialect = csv.Sniffer().sniff(csvfile.read(1024), delimiters=";,\t")
                except csv.Error:
                    logger.critical(f"Could not determine the delimiter in the organism tabulated file.")
                    exit(1)
                csvfile.seek(0)
                reader = csv.reader(csvfile, dialect)
                org_mapping = {i[0]:i[1] for i in reader}
        else:
            org_mapping = {i:org for i in all_genomes}

        # check that all data is here
        try:
            assert all_genomes.issubset(set(org_mapping.keys()))
        except AssertionError:
            logger.critical(f"Genomes in {nucleic_fasta} do not match the genomes IDs of {org} (first column, no extension to the genome names).")
            sys.exit(1)
        try:
            assert all(ext == 'fna' for ext in [get_extension(i) for i in os.listdir(nucleic_fasta)])
        except AssertionError:
            logger.critical(f"Genomes dir {nucleic_fasta} must contain only '.fna' files")
            sys.exit(1)
        #TODO later: be less hard on that constraint, just check that every genome foo.fna has a foo.faa in protein_fasta, a foo.tsv in annot etc. This could make possible for a user to give the same dir for all inputs. Or ignore the extension and ensure thee is a foo.* in annot, a foo.* in proteome etc.
        try:
            set([get_basename(i) for i in os.listdir(protein_fasta)]) == all_genomes
        except AssertionError:
            logger.critical(f"Genomes names in {nucleic_fasta} do not match the names in {protein_fasta}.")
            sys.exit(1)
        try:
            assert all(ext == 'faa' for ext in [get_extension(i) for i in os.listdir(protein_fasta)])
        except AssertionError:
            logger.critical(f"Proteomes dir {protein_fasta} must contain only '.faa' files")
            sys.exit(1)
        if os.path.isdir(annot):
            try:
                assert set([get_basename(i) for i in os.listdir(annot)]) == all_genomes
            except AssertionError:
                logger.critical(f"Genomes names in {nucleic_fasta} do not match the names in {annot}.")
                sys.exit(1)
            try:
                assert all(ext == 'tsv' for ext in [get_extension(i) for i in os.listdir(annot)])
            except AssertionError:
                logger.critical(f"Annotations dir {annot} must contain only '.tsv' files")
                sys.exit(1)
        if gff:
            try:
                assert set([get_basename(i) for i in os.listdir(gff)]) == all_genomes
            except AssertionError:
                logger.critical(f"Genomes names in {nucleic_fasta} do not match the names in {gff}.")
                sys.exit(1)
            try:
                assert all(ext == 'gff' for ext in [get_extension(i) for i in os.listdir(gff)])
            except AssertionError:
                logger.critical(f"GFF dir {gff} must contain only '.gff' files")
                sys.exit(1)

        multiprocess_data = []

        # Query Gene Ontology to extract namespaces and alternative IDs.
        # go_namespaces: Dictionary GO id as term and GO namespace as value.
        # go_alternatives: Dictionary GO id as term and GO alternatives id as value.
        go_namespaces, go_alternatives = create_GO_namespaces_alternatives(gobasic)

        if gff and not one_annot_file:
            for genome_id in all_genomes:
                nucleic_fasta_path = os.path.join(nucleic_fasta, genome_id+'.fna')
                protein_fasta_path = os.path.join(protein_fasta, genome_id+'.faa')
                annot_path = os.path.join(annot, genome_id+'.tsv')
                gff_path = os.path.join(gff, genome_id+'.gff')
                gbk_output_path = os.path.join(output_path, genome_id+'.gbk')
                multiprocess_data.append([nucleic_fasta_path, protein_fasta_path, annot_path,
                                            gff_path, org_mapping[genome_id], gbk_output_path,
                                            (go_namespaces, go_alternatives)])
            gbk_pool.starmap(genomes_to_gbk.main, multiprocess_data)

        elif gff and one_annot_file:
            annot_genecat = dict(read_annotation(annot))
            for genome_id in all_genomes:
                nucleic_fasta_path = os.path.join(nucleic_fasta, genome_id+'.fna')
                protein_fasta_path = os.path.join(protein_fasta, genome_id+'.faa')
                gff_path = os.path.join(gff, genome_id+'.gff')
                gbk_output_path = os.path.join(output_path, genome_id+'.gbk')
                multiprocess_data.append([nucleic_fasta_path, protein_fasta_path, annot_genecat,
                                            gff_path, org_mapping[genome_id], gbk_output_path,
                                            (go_namespaces, go_alternatives)])
            gbk_pool.starmap(genomes_to_gbk.main, multiprocess_data)

        elif not gff and not one_annot_file:
            for genome_id in all_genomes:
                nucleic_fasta_path = os.path.join(nucleic_fasta, genome_id+'.fna')
                protein_fasta_path = os.path.join(protein_fasta, genome_id+'.faa')
                annot_path = os.path.join(annot, genome_id+'.tsv')
                gbk_output_path = os.path.join(output_path, genome_id+'.gbk')
                multiprocess_data.append([nucleic_fasta_path, protein_fasta_path, annot_path,
                                            org_mapping[genome_id], gbk_output_path,
                                            (go_namespaces, go_alternatives), merge_genes_fake_contig])
            gbk_pool.starmap(genes_to_gbk.faa_to_gbk, multiprocess_data)

        elif not gff and one_annot_file:
            all_genomes = set(all_genomes) - set(os.listdir(output_path))
            # read annotation of gene catalogue
            annot_genecat = dict(read_annotation(annot))
            for genome_id in all_genomes:
                nucleic_fasta_path = os.path.join(nucleic_fasta, genome_id+'.fna')
                protein_fasta_path = os.path.join(protein_fasta, genome_id+'.faa')
                gbk_output_path = os.path.join(output_path, genome_id+'.gbk')
                multiprocess_data.append([nucleic_fasta_path, protein_fasta_path, annot_genecat,
                                            org_mapping[genome_id], gbk_output_path,
                                            (go_namespaces, go_alternatives), merge_genes_fake_contig])
            gbk_pool.starmap(genes_to_gbk.main, multiprocess_data)

        gbk_pool.close()
        gbk_pool.join()
