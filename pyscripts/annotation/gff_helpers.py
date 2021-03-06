import pandas as pd
import gffutils
import os
from collections import defaultdict

GTF_NAMES = ['chrom','source','feature_type','start','end','.','strand','.','attributes']


def get_attribute_type_set(gtf_file, attribute_type):
    """
    from a GTF file, extract the set of attribute_types
    (attribute_types is one of those fields contained within the 9th column)
    This might be useful for figuring out the priority for annotation.
    
    Parameters
    ----------
    gtf_file : basestring
    attribute_type : basestring

    Returns
    -------

    """

    gtf_df = pd.read_table(
        gtf_file,
        names=GTF_NAMES,
        comment='#'
    )
    regex_filter = '{} \"([\w\s\d -]+)\"'.format(attribute_type)
    return set(gtf_df['attributes'].str.extract(regex_filter, expand=False))


def get_feature_type_set_from_df(df):
    """
    from a GTF file, extract the set of feature_types
    (feature_types is the third column, normally)
    This might be useful for figuring out the priority for annotation.

    Parameters
    ----------
    df : pandas.DataFrame()

    Returns
    -------

    """
    return set(df['feature_type'])


def get_attribute_type_set_from_df(df, attribute_type):
    """
    from a GTF file, extract the set of attribute_types
    (attribute_types is one of those fields contained within the 9th column)
    This might be useful for figuring out the priority for annotation.

    Parameters
    ----------
    df : pandas.DataFrame()
    attribute_type : basestring

    Returns
    -------

    """

    regex_filter = '{} \"([\w\s\d -]+)\"'.format(attribute_type)
    return set(df['attributes'].str.extract(regex_filter, expand=False))


def build_db(
        annotation_file, annotation_db_file, force=False,
        exon_featuretype='exon', grandparent_featuretype='gene'
):
    """
    Builds a database file from a GTF/GFF annotation file.
    Automatically infers introns (because this is useful in general,
    but also necessary for eCLIP annotation).
    
    Note this function takes awhile to build for human gencode annotations...
    
    Parameters
    ----------
    annotation_file : basestring
    annotation_db_file : basestring
    force: bool
        raises exception if db (annotation_db_file) exists
    exon_featuretype : basestring
        inverse of this featuretype becomes the intron
        (default: exon)
    grandparent_featuretype : basestring
        boundary of this featuretype used to infer introns
        (default: gene)
    Returns
    -------
    0 if successful, 1 if not.
    """
    try:
        gffutils.create_db(
            annotation_file, dbfn=annotation_db_file, force=force,
            keep_order=True, merge_strategy='merge',
            sort_attribute_values=True
        )

        infer_and_insert_introns(
            annotation_db_file,
            exon_featuretype=exon_featuretype,
            grandparent_featuretype=grandparent_featuretype
        )
        return 0
    except Exception as e:
        print(e)
        return 1


def infer_and_insert_introns(db_file, exon_featuretype='exon', grandparent_featuretype='gene'):
    db = gffutils.FeatureDB(db_file)
    introns = db.create_introns(
        exon_featuretype=exon_featuretype,
        grandparent_featuretype=grandparent_featuretype
    )
    db.update(introns)
    return 0




def gene_name_to_id(db):
    """
    given a gene name, returns a list of associated Gene IDs (one-to-many)
    
    Parameters
    ----------
    db : sqlite3 database

    Returns
    -------
    gene_name_dict : dict{list}
        dictionary of gene_name : [gene_ids]
    """

    genes = db.features_of_type('gene')
    gene_name_dict = defaultdict(list)
    for gene in genes:
        try:
            gene_name_dict[gene.attributes['gene_name'][0]].append(gene.attributes['gene_id'][0])
        except KeyError as e:
            print("Warning. Key not found for {}".format(gene))
            return 1
    return gene_name_dict


def gene_name_to_transcript(db):
    """
    given a gene name, returns a list of associated transcript IDs (one-to-many)
    
    Parameters
    ----------
    db : sqlite3 database

    Returns
    -------
    gene_name_dict : dict{list}
        dictionary of gene_name : [transcript_ids]
    """

    genes = db.features_of_type('transcript')
    gene_name_dict = defaultdict(list)
    for gene in genes:
        try:
            gene_name_dict[gene.attributes['gene_name'][0]].append(gene.attributes['transcript_id'][0])
        except KeyError as e:
            print("Warning. Key not found for {}".format(gene))
            return 1
    return gene_name_dict


def gene_id_to_transcript(db):
    """
    given a gene name, returns a list of associated transcript IDs (one-to-many)

    Parameters
    ----------
    db : sqlite3 database

    Returns
    -------
    gene_name_dict : dict{list}
        dictionary of gene_name : [transcript_ids]
    """

    genes = db.features_of_type('transcript')
    gene_name_dict = defaultdict(list)
    for gene in genes:
        try:
            gene_name_dict[gene.attributes['gene_id'][0]].append(gene.attributes['transcript_id'][0])
        except KeyError as e:
            print("Warning. Key not found for {}".format(gene))
            return 1
    return gene_name_dict


def id_to_exons(db, identifier):
    """
    takes the gene or transcript id and returns exon positions
    
    Parameters
    ----------
    db : sqlite3 database
    identifier : basestring
        gene_id or gene_name

    Returns
    -------
    exons : list
        list of exons<Feature> corresponding to the gene
    """

    exons = []
    for i in db.children(identifier, featuretype='exon', order_by='start'):
        exons.append(i)
    return exons


def position_to_features(db, chrom, start, end, strand='', completely_within=True):
    """
    
    takes a coordinate and returns all the features overlapping 
    (either completely contained or partially overlapping the region).
    
    Parameters
    ----------
    db : sqlite3 database
    chrom : basestring
    start : int
    end : int
    strand : basestring
    completely_within : bool
        True if the features returned must be completely contained
        within the region. False if the features need only to be
        partially overlapping the region.
        
    Returns
    -------
    region_list: list
        list of Features corresponding to overlapping/contained
        features intersecting a region.
    """

    if strand == '+' or strand == '-':
        return list(
            db.region(
                region=(chrom, start, end), strand=strand, completely_within=completely_within
            )
        )
    else:
        return list(
            db.region(
                region=(chrom, start, end), completely_within=completely_within
            )
        )


def bedtool_to_features(db, interval, completely_within):
    """
    
    takes a coordinate and returns all the features overlapping 
    (either completely contained or partially overlapping the region).
    
    Parameters
    ----------
    db : sqlite3 database
    interval : pybedtools.Interval
        interval object
    completely_within : bool
        True if the features returned must be completely contained
        within the region. False if the features need only to be
        partially overlapping the region.
        
    Returns
    -------
    region_list: list
        list of Features corresponding to overlapping/contained
        features intersecting a region.
    """
    return position_to_features(
        db,
        interval.chrom,
        interval.start,
        interval.end,
        interval.strand,
        completely_within
    )

